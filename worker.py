import argparse
import re
import time
from typing import Dict, Any, List
import database
import media_engine
import seo_engine

DEFAULT_TRENDING_TOPICS = [
    "How AI Agents Are Replacing Traditional Apps in 2026",
    "Why Solid-State Batteries Change Electric Vehicles Forever",
    "The Hidden Psychology Behind High-Performing Habits",
]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return slug[:40] or "video"


def run_pipeline_for_topic(topic: str) -> Dict[str, Any]:
    """
    Orchestrate the end-to-end creation pipeline for a single topic:
    1. Generate SEO metadata, 3-tier tags, ~230-word script, and Pexels queries via Gemini 1.5 Flash.
    2. Synthesize voiceover via edge-tts and assemble vertical 1080x1920 video with Pexels b-roll.
    3. Insert draft into SQLite (`studio.db`) with status 'PENDING_REVIEW'.
    """
    database.init_db()

    seo_package = seo_engine.generate_seo_and_script(topic)
    timestamp = int(time.time())
    output_filename = f"{_slugify(topic)}_{timestamp}.mp4"

    video_path, duration = media_engine.assemble_video(
        script=seo_package["script"],
        pexels_queries=seo_package["pexels_queries"],
        output_filename=output_filename,
    )

    video_id = database.insert_video(
        topic=topic,
        title=seo_package["title"],
        description=seo_package["description"],
        tags=seo_package["tags"],
        script=seo_package["script"],
        video_path=video_path,
        duration=duration,
        status="PENDING_REVIEW",
    )

    record = database.get_video_by_id(video_id)
    return record or {"id": video_id, "topic": topic, "video_path": video_path}


def run_daily_batch(topics: List[str] | None = None) -> List[Dict[str, Any]]:
    """Run the pipeline across a list of trending topics."""
    target_topics = topics or DEFAULT_TRENDING_TOPICS
    results = []
    for topic in target_topics:
        print(f"[Worker] Generating draft for topic: {topic}")
        draft = run_pipeline_for_topic(topic)
        print(
            f"[Worker] Created draft #{draft['id']} ({draft.get('duration')}s) -> {draft.get('video_path')}"
        )
        results.append(draft)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Automated YouTube Content Studio Worker Pipeline"
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="Generate a single vertical video draft for the specified topic.",
    )
    args = parser.parse_args()

    if args.topic:
        run_pipeline_for_topic(args.topic)
    else:
        run_daily_batch()
