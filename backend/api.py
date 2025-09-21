from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pipeline.story_maker import StoryMaker
from models.models import Story
from diffusers import StableDiffusionXLPipeline
import torch
import asyncio
import os

app = FastAPI(title="GenAI Story API")

storymaker = None
storymaker_lock = asyncio.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading Stable Diffusion pipeline...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/sdxl-turbo",
    torch_dtype=torch.float32,
)
pipe = pipe.to("cpu")
print("Pipeline loaded!")

async def get_storymaker():
    """
    Returns a singleton instance of StoryMaker.
    Ensures thread-safety using an asyncio lock to prevent race conditions
    when initializing the instance.
    """
    global storymaker
    async with storymaker_lock:
        if storymaker is None:
            storymaker = StoryMaker(pipe)
    return storymaker


class GenerateRequest(BaseModel):
    """
    Request schema for generating a story.
    - genre: The genre of the story (default: fantasy).
    - num_scenes: Number of scenes to generate (default: 5).
    """
    genre: str = "fantasy"
    num_scenes: int = 5


@app.get("/download_file/")
async def download_file(path: str = Query(..., description="Path to the file to download")):
    """
    Endpoint to download a generated file.
    
    Args:
        path (str): The absolute or relative file path to download.
    
    Returns:
        FileResponse: Returns the file with correct media type.
    
    Raises:
        HTTPException 404: If the file does not exist.
    """
    if os.path.exists(path):
        filename = os.path.basename(path)
        media_type = "video/mp4" if filename.endswith(".mp4") else "text/plain"

        return FileResponse(
            path=path,
            filename=filename,
            media_type=media_type
        )
    else:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")


@app.post("/generate_story/")
async def generate_story_api(params: GenerateRequest):
    """
    Endpoint to generate a story and associated assets (scenes, prompts, video).

    Process:
    1. Retrieves or initializes the StoryMaker instance.
    2. Uses StoryMaker to generate story content.
    3. Fetches the generated story from the database (MongoEngine Story model).
    4. Returns structured metadata and asset paths.

    Args:
        params (GenerateRequest): Genre and number of scenes to generate.

    Returns:
        dict: Metadata of the generated story including title, genre, scenes,
              image prompts, folder path, and video file.

    Raises:
        HTTPException 500: If story generation or database retrieval fails.
    """
    try:
        sm = await get_storymaker()
        sm.genre = params.genre
        sm.num_scenes = params.num_scenes

        story_data = await asyncio.to_thread(sm.create_story)

        story_doc = Story.objects(story_id=story_data["story_id"]).first()
        if not story_doc:
            raise HTTPException(status_code=500, detail="Failed to retrieve story from database")

        response_data = {
            "story_id": story_doc.story_id,
            "title": story_doc.title,
            "genre": story_doc.genre,
            "story_idea": story_doc.story_idea,
            "scenes": [
                {"scene": s.scene, "summary": s.summary, "description": s.description}
                for s in story_doc.scenes
            ],
            "image_prompts": story_doc.image_prompts,
            "folder": story_doc.folder,
            "video_file": story_data["video_file"],
        }

        return {
            "metadata": response_data,
            "message": f"Story in '{params.genre}' generated successfully!"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
