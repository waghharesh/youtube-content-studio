from pathlib import Path
import streamlit as st
import database
import worker
import youtube_client

st.set_page_config(
    page_title="Automated YouTube Content Studio",
    page_icon="🎬",
    layout="wide",
)

database.init_db()

st.title("🎬 100% Free Automated YouTube Content Studio")
st.caption(
    "Gemini 1.5 Flash • Edge-TTS (`en-US-ChristopherNeural`) • Pexels Stock Video • MoviePy • YouTube Data API v3"
)

tab_review, tab_generate, tab_archive = st.tabs(
    ["📝 Review Queue", "⚡ Manual Generation", "📺 Published Archive"]
)

with tab_review:
    st.subheader("Pending Peer Review Queue")
    pending_videos = database.get_videos_by_status("PENDING_REVIEW")

    if not pending_videos:
        st.info(
            "No videos are currently waiting in `PENDING_REVIEW`. Use the **Manual Generation** tab or run `python worker.py` to generate drafts."
        )
    else:
        for vid in pending_videos:
            with st.expander(
                f"#{vid['id']} — {vid['title']} ({vid['duration']:.1f}s) | Topic: {vid['topic']}",
                expanded=True,
            ):
                col_preview, col_meta = st.columns([1, 2])

                with col_preview:
                    video_file = Path(vid["video_path"])
                    if video_file.exists():
                        st.video(str(video_file))
                    else:
                        st.warning(f"Video file not found on disk: `{vid['video_path']}`")
                    st.markdown(f"**Duration:** `{vid['duration']:.2f}s`")
                    st.markdown(f"**Status:** `{vid['status']}`")

                with col_meta:
                    with st.form(key=f"review_form_{vid['id']}"):
                        edited_title = st.text_input(
                            "Title", value=vid["title"], max_chars=100
                        )
                        edited_description = st.text_area(
                            "Description", value=vid["description"], height=120
                        )
                        edited_tags_str = st.text_input(
                            "Tags (comma-separated)",
                            value=", ".join(vid.get("tags_list", [])),
                        )
                        st.text_area(
                            "Spoken Script (Read-only)",
                            value=vid["script"],
                            height=140,
                            disabled=True,
                        )

                        btn_col1, btn_col2, btn_col3 = st.columns(3)
                        save_clicked = btn_col1.form_submit_button("💾 Save Edits")
                        approve_clicked = btn_col2.form_submit_button(
                            "🚀 Approve & Publish to YouTube"
                        )
                        reject_clicked = btn_col3.form_submit_button("🗑️ Reject Draft")

                        parsed_tags = [
                            t.strip() for t in edited_tags_str.split(",") if t.strip()
                        ]

                        if save_clicked:
                            database.update_video_metadata(
                                vid["id"],
                                title=edited_title,
                                description=edited_description,
                                tags=parsed_tags,
                            )
                            st.success(f"Saved metadata updates for video #{vid['id']}.")
                            st.rerun()

                        if approve_clicked:
                            database.update_video_metadata(
                                vid["id"],
                                title=edited_title,
                                description=edited_description,
                                tags=parsed_tags,
                            )
                            try:
                                with st.spinner("Uploading video to YouTube..."):
                                    yt_id = youtube_client.upload_video_to_youtube(
                                        video_path=vid["video_path"],
                                        title=edited_title,
                                        description=edited_description,
                                        tags=parsed_tags,
                                    )
                                database.update_video_status(
                                    vid["id"],
                                    status="PUBLISHED",
                                    youtube_video_id=yt_id,
                                )
                                st.success(
                                    f"Published to YouTube! Video ID: `{yt_id}`"
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(f"YouTube upload failed: {exc}")

                        if reject_clicked:
                            database.update_video_status(vid["id"], status="REJECTED")
                            st.warning(f"Rejected draft #{vid['id']}.")
                            st.rerun()

with tab_generate:
    st.subheader("Generate New Vertical Video Draft (1080x1920)")
    with st.form("manual_generation_form"):
        topic_input = st.text_input(
            "Trending Topic / Video Idea",
            placeholder="e.g., Why Quantum Computing Just Hit a Major Milestone",
        )
        generate_submitted = st.form_submit_button("✨ Run End-to-End Pipeline")

        if generate_submitted:
            if not topic_input.strip():
                st.error("Please enter a topic before running the pipeline.")
            else:
                try:
                    with st.spinner(
                        "Generating SEO & script with Gemini 1.5 Flash, synthesizing Edge-TTS voiceover, fetching Pexels b-roll, and rendering 1080x1920 MP4..."
                    ):
                        draft = worker.run_pipeline_for_topic(topic_input.strip())
                    st.success(
                        f"Draft #{draft['id']} created and added to the Review Queue (`PENDING_REVIEW`)!"
                    )
                except Exception as exc:
                    st.error(f"Pipeline execution error: {exc}")

with tab_archive:
    st.subheader("Published & Archived Videos")
    published_videos = database.get_videos_by_status("PUBLISHED")
    rejected_videos = database.get_videos_by_status("REJECTED")

    st.markdown("### ✅ Published to YouTube")
    if not published_videos:
        st.info("No videos have been published yet.")
    else:
        for pub in published_videos:
            yt_id = pub.get("youtube_video_id") or ""
            yt_url = f"https://www.youtube.com/watch?v={yt_id}" if yt_id else ""
            with st.container(border=True):
                st.markdown(f"#### #{pub['id']} — {pub['title']}")
                st.write(f"**Topic:** {pub['topic']} | **Duration:** {pub['duration']:.1f}s")
                if yt_url:
                    st.markdown(f"**YouTube Link:** [{yt_url}]({yt_url})")
                st.caption(f"Tags: {', '.join(pub.get('tags_list', []))}")

    if rejected_videos:
        with st.expander(f"🗑️ Rejected Drafts ({len(rejected_videos)})"):
            for rej in rejected_videos:
                st.write(f"- **#{rej['id']}** `{rej['title']}` (Topic: {rej['topic']})")
