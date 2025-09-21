import requests
import re
import uuid
import time
import os
from pathlib import Path
from diffusers import StableDiffusionXLPipeline
import torch
from PIL import Image
from gtts import gTTS
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip

from models.models import Story, Scene

hf_token = os.getenv("HUGGINGFACE_TOKEN")

class StoryMaker:
    OLLAMA_URL = "http://ollama:11434/api/generate"
    MODEL_NAME = "llama2"

    def __init__(
        self,
        pipe,
        genre="fantasy",
        num_scenes=5,
        max_retries=3,
        # model_id="stabilityai/sdxl-turbo",
        # model_id="runwayml/stable-diffusion-v1-5",
        output_dir="story_outputs",
    ):
        self.genre = genre.strip().lower()
        self.num_scenes = num_scenes
        self.max_retries = max_retries
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pipe = pipe

    # === LLaMA2 utils ===
    def query_llama2(self, prompt):
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.OLLAMA_URL,
                    json={"model": self.MODEL_NAME, "prompt": prompt, "stream": False},
                )
                if response.status_code == 200:
                    return response.json()["response"].strip()
                else:
                    print(f"Attempt {attempt+1}: Ollama returned {response.status_code}")
            except Exception as e:
                print(f"Attempt {attempt+1}: Error {e}")
            time.sleep(2)
        raise Exception("Failed to get response from Ollama after retries.")

    # === Story generation pieces ===
    def generate_story_idea(self):
        prompt = (
            f"Give me one unique, original short story idea in the {self.genre} genre. "
            f"Keep it 2-3 sentences and strongly reflect the tone of {self.genre}."
        )
        return self.query_llama2(prompt)

    def validate_story(self, idea):
        prompt = (
            f"Rate this {self.genre} story idea for creativity and relevance (1-10 each) and explain why:\n\n{idea}"
        )
        return self.query_llama2(prompt)

    def generate_title(self, story_idea):
        prompt = (
            f"Based on this story idea from the {self.genre} genre, give me a compelling title. "
            f"Return only the title:\n\n{story_idea}"
        )
        return self.query_llama2(prompt)

    def generate_scenes(self, story_idea):
        prompt = (
            f"Break the following {self.genre} story into {self.num_scenes} detailed scenes.\n"
            f"Format each like this:\nScene 1: <one-sentence summary>\n"
            f"Description: <a few sentences describing the setting and events>\n"
            f"Keep each description within 50 words.\n"
            f"Reflect the tone and aesthetic of {self.genre}.\n\n"
            f"{story_idea}"
        )
        return self.query_llama2(prompt)

    def parse_scenes(self, scenes_text):
        pattern = r"Scene\s*(\d+):\s*(.*?)\nDescription:\s*(.*?)(?=\nScene\s*\d+:|\Z)"
        matches = re.findall(pattern, scenes_text, re.DOTALL)
        scenes = [
            {"scene": int(num), "summary": summary.strip(), "description": description.strip()}
            for num, summary, description in matches
        ]
        return scenes

    def generate_image_prompts(self, scenes):
        descriptions = "\n".join([f"Scene {s['scene']}: {s['description']}" for s in scenes])
        prompt = (
            f"Convert the following {self.genre} scene descriptions into highly detailed, cinematic prompts for AI art generation. "
            f"Use terms like 'ultra-detailed', '8K', 'cinematic lighting', 'concept art style'. "
            f"Return one prompt per scene, in the format:\nScene X: <prompt>\n\n{descriptions}"
        )
        raw_prompts = self.query_llama2(prompt)
        pattern = r"Scene\s*(\d+):\s*(.*?)(?=\nScene\s*\d+:|\Z)"
        matches = re.findall(pattern, raw_prompts, re.DOTALL)
        prompts = {int(num): text.strip() for num, text in matches}
        return prompts, raw_prompts

    # === Media generation ===
    def generate_images_and_audio(self, image_prompts, scenes, output_folder, voice="en"):
        for scene in scenes:
            scene_num = scene["scene"]
            prompt = image_prompts.get(scene_num)
            description = scene.get("description", "").strip()

            # Image
            print(f"🎨 Generating image for Scene {scene_num}...")
            try:
                image = self.pipe(prompt, num_inference_steps=1, guidance_scale=0.0).images[0]
                img_path = Path(output_folder) / f"scene_{scene_num}.png"
                image.save(img_path)
            except Exception as e:
                print(f"Failed to generate image for Scene {scene_num}: {e}")

            # Audio
            if description:
                mp3_path = Path(output_folder) / f"scene_{scene_num}.mp3"
                if not mp3_path.exists():
                    print(f"🔊 Narrating Scene {scene_num}...")
                    try:
                        tts = gTTS(text=description, lang=voice)
                        tts.save(str(mp3_path))
                    except Exception as e:
                        print(f"Failed to generate audio for Scene {scene_num}: {e}")

    # === Video creation ===
    def create_video_for_project(self, project_folder, output_path):
        scenes = []
        scene_nums = sorted(
            int(f.name.split("_")[1].split(".")[0])
            for f in project_folder.iterdir()
            if f.name.startswith("scene_") and f.suffix == ".png"
        )

        for scene_num in scene_nums:
            img_path = project_folder / f"scene_{scene_num}.png"
            audio_path = project_folder / f"scene_{scene_num}.mp3"
            if not audio_path.exists():
                print(f"Missing audio for Scene {scene_num}")
                continue

            audio_clip = AudioFileClip(str(audio_path))
            img_clip = ImageClip(str(img_path), duration=audio_clip.duration)
            video_clip = CompositeVideoClip([img_clip])
            video_clip.audio = audio_clip
            scenes.append(video_clip)

        if not scenes:
            print("No scenes found for video.")
            return None

        final_clip = concatenate_videoclips(scenes, method="compose")
        final_clip.write_videofile(str(output_path), fps=24)
        return output_path

    # === Utilities ===
    def sanitize_filename(self, title):
        return re.sub(r'[\\/*?:"<>|]', "_", title)

    # === Mongo save ===
    def save_story_to_mongo(self, title, idea, scenes, raw_scenes_text, image_prompts, raw_image_prompts, output_folder):
        story_id = str(uuid.uuid4())[:8]

        # Ensure all image_prompts keys are strings
        image_prompts_str_keys = {str(k): v for k, v in image_prompts.items()}

        # Create embedded Scene documents
        scene_docs = [
            Scene(scene=s["scene"], summary=s["summary"], description=s["description"])
            for s in scenes
        ]

        # Create and save the Story document
        story_doc = Story(
            story_id=story_id,
            title=title,
            genre=self.genre,
            story_idea=idea,
            raw_scenes_text=raw_scenes_text,
            scenes=scene_docs,
            image_prompts=image_prompts_str_keys,
            raw_image_prompts=raw_image_prompts,
            folder=str(output_folder)
        )
        story_doc.save()
        return story_doc

    # === Full pipeline ===
    def create_story(self, voice="en"):
        print("Generating story idea...")
        story_idea = self.generate_story_idea()

        print("Validating story idea...")
        validation = self.validate_story(story_idea)
        print(f"Validation result:\n{validation}\n")

        print("Generating title...")
        title = self.generate_title(story_idea)

        print("Generating scenes...")
        raw_scenes = self.generate_scenes(story_idea)
        scenes = self.parse_scenes(raw_scenes)

        print("Generating image prompts...")
        image_prompts, raw_image_prompts = self.generate_image_prompts(scenes)

        folder_name = self.sanitize_filename(title)
        output_folder = Path("story_outputs") / folder_name
        output_folder.mkdir(parents=True, exist_ok=True)

        # Save to Mongo
        story_doc = self.save_story_to_mongo(
            title, story_idea, scenes, raw_scenes, image_prompts, raw_image_prompts, output_folder
        )

        print("Generating images and audio...")
        self.generate_images_and_audio(image_prompts, scenes, output_folder, voice)

        print("Creating video...")
        output_video = output_folder / f"{self.sanitize_filename(title)}.mp4"
        self.create_video_for_project(output_folder, output_video)

        print(f"Story and video complete: {output_video}")

        return {
            "story_id": story_doc.story_id,
            "story_folder": str(output_folder),
            "video_file": str(output_video),
            "title": title,
            "story_idea": story_idea,
            "validation": validation,
            "scenes": scenes,
            "image_prompts": image_prompts
        }
