import mongoengine as me
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

me.connect(
    db=os.getenv("MONGO_DB"),
    username=os.getenv("MONGO_USER"),
    password=os.getenv("MONGO_PASSWORD"),
    host=os.getenv("MONGO_HOST"),
    authentication_source=os.getenv("MONGO_AUTH_SOURCE")
)

class Scene(me.EmbeddedDocument):
    """
    Represents an individual scene in a story.

    Attributes:
        scene (int): Numeric identifier of the scene (e.g., 1, 2, 3).
        summary (str): A short summary of the scene.
        description (str): A detailed description of the scene.
    """
    scene = me.IntField(required=True)
    summary = me.StringField(required=True)
    description = me.StringField(required=True)


class Story(me.Document):
    """
    Represents a story document stored in MongoDB.

    Attributes:
        story_id (str): Unique identifier for the story.
        title (str): Title of the story.
        genre (str): Genre of the story (e.g., Fantasy, Sci-Fi).
        story_idea (str): High-level idea or concept for the story.
        raw_scenes_text (str): Full unprocessed text of scenes before splitting.

        scenes (list[Scene]): List of embedded Scene documents.
        image_prompts (dict): Key-value mapping for generated image prompts.
        raw_image_prompts (str): Raw string containing all image prompts.

        folder (str): Optional folder reference for storing related assets.
        created_at (datetime): Timestamp of when the story was created.
    """
    story_id = me.StringField(required=True, unique=True)
    title = me.StringField(required=True)
    genre = me.StringField(required=True)
    story_idea = me.StringField(required=True)
    raw_scenes_text = me.StringField(required=True)

    scenes = me.EmbeddedDocumentListField(Scene)
    image_prompts = me.MapField(field=me.StringField())
    raw_image_prompts = me.StringField()

    folder = me.StringField()
    created_at = me.DateTimeField(default=datetime.utcnow)