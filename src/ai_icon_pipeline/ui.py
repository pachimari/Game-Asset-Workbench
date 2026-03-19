from __future__ import annotations

from pathlib import Path
import json
import sys

import streamlit as st

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ai_icon_pipeline.config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
    from ai_icon_pipeline.pipeline import (
        approve_step,
        edit_brief,
        edit_prompt,
        rollback_step,
        run_pipeline,
        run_step,
        set_current_version,
    )
    from ai_icon_pipeline.storage import (
        create_task,
        item_dir,
        list_artifacts,
        list_items,
        list_tasks,
        load_artifact,
        load_item,
        load_item_events,
        load_task,
        load_task_events,
    )
else:
    from .config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
    from .pipeline import (
        approve_step,
        edit_brief,
        edit_prompt,
        rollback_step,
        run_pipeline,
        run_step,
        set_current_version,
    )
    from .storage import (
        create_task,
        item_dir,
        list_artifacts,
        list_items,
        list_tasks,
        load_artifact,
        load_item,
        load_item_events,
        load_task,
        load_task_events,
    )


STEP_LABELS = {
    STEP_BRIEF_GENERATION: "Brief",
    STEP_IMAGE_PROMPT: "Prompt",
    STEP_IMAGE_GENERATION: "Image",
}


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .app-shell {
          padding: 0.6rem 0 1.2rem 0;
        }
        .hero {
          background: linear-gradient(135deg, #f6f0df 0%, #d7ebe7 52%, #d8e1f7 100%);
          border: 1px solid rgba(44, 62, 80, 0.12);
          border-radius: 20px;
          padding: 1.1rem 1.2rem;
          margin-bottom: 1rem;
        }
        .hero h1 {
          font-size: 1.9rem;
          margin: 0 0 0.35rem 0;
          color: #1f2937;
        }
        .hero p {
          margin: 0;
          color: #334155;
        }
        .panel {
          border: 1px solid rgba(30, 41, 59, 0.12);
          border-radius: 18px;
          padding: 0.9rem 1rem;
          background: rgba(255, 255, 255, 0.74);
          box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
          margin-bottom: 0.9rem;
        }
        .kicker {
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-size: 0.75rem;
          color: #64748b;
        }
        .stat {
          border-radius: 16px;
          padding: 0.8rem 0.9rem;
          background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(246,248,251,0.9));
          border: 1px solid rgba(100, 116, 139, 0.15);
        }
        .stat strong {
          display: block;
          font-size: 1.15rem;
          color: #0f172a;
        }
        .code-box {
          background: #0f172a;
          color: #e2e8f0;
          padding: 0.75rem 0.9rem;
          border-radius: 14px;
          overflow-x: auto;
          font-family: Menlo, Monaco, monospace;
          font-size: 0.84rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _show_json(payload: dict | list) -> None:
    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")


def _task_label(task: dict) -> str:
    return f"{task['task_id']} · {task.get('task_name', 'Untitled')} · {task.get('status', 'unknown')}"


def _item_label(item: dict) -> str:
    title = item.get("title") or item.get("asset_type", "item")
    return f"{item['item_id']} · {title} · {item.get('status', 'unknown')}"


def _artifact_or_none(task_id: str, item_id: str, step: str, version: str | None) -> dict | None:
    if not version:
        return None
    try:
        return load_artifact(task_id, item_id, step, version)
    except ValueError:
        return None


def _render_task_creation() -> None:
    with st.sidebar.expander("Create Task", expanded=False):
        create_mode = st.radio("Mode", ["Single Item", "Batch JSON"], key="create_mode")

        if create_mode == "Single Item":
            with st.form("create_single_task_form"):
                task_name = st.text_input("Task Name", value="Untitled icon batch")
                project_context = st.text_input("Project Context", value="通用项目")
                asset_domain = st.text_input("Asset Domain", value="game_icon_assets")
                asset_type = st.text_input("Asset Type", value="generic_icon")
                title = st.text_input("Title")
                description = st.text_area("Description", height=120)
                category = st.text_input("Category")
                extra_context = st.text_area("Extra Context", height=80)
                submitted = st.form_submit_button("Create Task", use_container_width=True)
            if submitted:
                if not description.strip():
                    st.sidebar.error("Description is required.")
                else:
                    task = create_task(
                        task_name=task_name,
                        project_context=project_context,
                        asset_domain=asset_domain,
                        items=[
                            {
                                "asset_type": asset_type,
                                "title": title,
                                "description": description,
                                "category": category,
                                "extra_context": extra_context,
                            }
                        ],
                    )
                    st.sidebar.success(f"Created {task['task_id']}")
                    st.session_state["selected_task_id"] = task["task_id"]
                    _rerun()
        else:
            with st.form("create_batch_task_form"):
                example = {
                    "task_name": "三国奇幻首批图标",
                    "project_context": "三国奇幻",
                    "asset_domain": "game_icon_assets",
                    "items": [
                        {
                            "asset_type": "skill_icon",
                            "title": "雷暴",
                            "description": "对敌人造成雷电伤害并附带麻痹效果",
                            "category": "combat",
                        }
                    ],
                }
                batch_text = st.text_area(
                    "Batch JSON",
                    value=json.dumps(example, ensure_ascii=False, indent=2),
                    height=260,
                )
                submitted = st.form_submit_button("Create Batch Task", use_container_width=True)
            if submitted:
                try:
                    payload = json.loads(batch_text)
                    task = create_task(
                        task_name=payload.get("task_name", "Untitled icon batch"),
                        project_context=payload.get("project_context", "通用项目"),
                        asset_domain=payload.get("asset_domain", "game_icon_assets"),
                        items=payload["items"],
                        style_spec=payload.get("style_spec"),
                        runtime_config=payload.get("runtime_config"),
                    )
                except Exception as exc:
                    st.sidebar.error(str(exc))
                else:
                    st.sidebar.success(f"Created {task['task_id']}")
                    st.session_state["selected_task_id"] = task["task_id"]
                    _rerun()


def _render_sidebar(tasks: list[dict]) -> str | None:
    st.sidebar.title("Workspace")
    st.sidebar.caption("Task list, item selector, and quick actions.")
    _render_task_creation()

    if not tasks:
        st.sidebar.info("No batch tasks found yet. Create one from the form above.")
        return None

    task_lookup = {task["task_id"]: task for task in tasks}
    current_task_id = st.session_state.get("selected_task_id")
    if current_task_id not in task_lookup:
        current_task_id = tasks[0]["task_id"]

    selected_label = st.sidebar.selectbox(
        "Task",
        options=[task["task_id"] for task in tasks],
        index=[task["task_id"] for task in tasks].index(current_task_id),
        format_func=lambda task_id: _task_label(task_lookup[task_id]),
        key="selected_task_id",
    )

    if st.sidebar.button("Refresh", use_container_width=True):
        _rerun()

    return selected_label


def _render_task_summary(task: dict, items: list[dict]) -> None:
    summary = task.get("items_summary", {})
    st.markdown(
        f"""
        <div class="hero">
          <div class="kicker">Task Workspace</div>
          <h1>{task.get('task_name', task['task_id'])}</h1>
          <p>{task.get('project_context', 'No project context')} · {task.get('asset_domain', 'game_icon_assets')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    stats = [
        ("Task Status", task.get("status", "unknown")),
        ("Items", str(task.get("item_count", len(items)))),
        ("Completed", str(summary.get("completed", 0))),
        ("In Progress", str(summary.get("in_progress", 0))),
    ]
    for col, (label, value) in zip(cols, stats):
        col.markdown(
            f'<div class="stat"><span class="kicker">{label}</span><strong>{value}</strong></div>',
            unsafe_allow_html=True,
        )

    task_rows = [
        {
            "item_id": item["item_id"],
            "title": item.get("title"),
            "asset_type": item.get("asset_type"),
            "status": item.get("status"),
            "brief": item["current_versions"].get("brief_generation"),
            "prompt": item["current_versions"].get("image_prompt"),
            "image": item["current_versions"].get("image_generation"),
        }
        for item in items
    ]
    st.markdown("### Items")
    st.dataframe(task_rows, use_container_width=True, hide_index=True)


def _current_action(status: str) -> tuple[str | None, str | None]:
    mapping = {
        "draft": ("run", STEP_BRIEF_GENERATION),
        "brief_generated": ("approve", STEP_BRIEF_GENERATION),
        "brief_approved": ("run", STEP_IMAGE_PROMPT),
        "prompt_generated": ("approve", STEP_IMAGE_PROMPT),
        "prompt_approved": ("run", STEP_IMAGE_GENERATION),
        "image_generated": ("approve", STEP_IMAGE_GENERATION),
    }
    return mapping.get(status, (None, None))


def _render_action_bar(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    status = item["status"]
    action_kind, step = _current_action(status)

    left, mid, right = st.columns([1.2, 1.2, 1.4])
    with left:
        if st.button("Auto Run Item", key=f"autorun-{item_id}", use_container_width=True):
            try:
                run_pipeline(task_id, item_id=item_id)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Item pipeline completed.")
                _rerun()
    with mid:
        if action_kind == "run":
            if st.button(f"Run {STEP_LABELS[step]}", key=f"run-{item_id}-{step}", use_container_width=True):
                try:
                    run_step(task_id, item_id, step)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Ran {step}.")
                    _rerun()
        elif action_kind == "approve":
            if st.button(
                f"Approve {STEP_LABELS[step]}",
                key=f"approve-{item_id}-{step}",
                use_container_width=True,
            ):
                try:
                    approve_step(task_id, item_id, step)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Approved {step}.")
                    _rerun()
        else:
            st.button("No Direct Action", disabled=True, use_container_width=True, key=f"idle-{item_id}")
    with right:
        if st.button("Refresh Item", key=f"refresh-{item_id}", use_container_width=True):
            _rerun()


def _render_current_outputs(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    brief = _artifact_or_none(task_id, item_id, STEP_BRIEF_GENERATION, item["current_versions"].get("brief_generation"))
    prompt = _artifact_or_none(task_id, item_id, STEP_IMAGE_PROMPT, item["current_versions"].get("image_prompt"))
    image = _artifact_or_none(task_id, item_id, STEP_IMAGE_GENERATION, item["current_versions"].get("image_generation"))

    left, right = st.columns([1.05, 0.95])
    with left:
        st.markdown("### Current Brief")
        if brief:
            _show_json(brief)
        else:
            st.info("No brief selected yet.")
        st.markdown("### Current Prompt")
        if prompt:
            _show_json(prompt)
        else:
            st.info("No prompt selected yet.")
    with right:
        st.markdown("### Current Images")
        image_root = item_dir(task_id, item_id) / "images"
        approved_path = image_root / "approved.png"
        if approved_path.exists():
            st.image(str(approved_path), caption="Approved Image", use_container_width=True)
        if image and image.get("output", {}).get("candidates"):
            cols = st.columns(min(3, len(image["output"]["candidates"])))
            for idx, candidate in enumerate(image["output"]["candidates"]):
                path = image_root / candidate["image_path"]
                if path.exists():
                    cols[idx % len(cols)].image(
                        str(path),
                        caption=f"{candidate['candidate_id']} · {item['current_versions'].get('image_generation')}",
                        use_container_width=True,
                    )
        elif not approved_path.exists():
            st.info("No image candidates generated yet.")


def _render_versions(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    st.markdown("### Versions")
    for step in [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION]:
        artifacts = list_artifacts(task_id, item_id, step)
        current = item["current_versions"].get(step)
        with st.expander(f"{STEP_LABELS[step]} Versions", expanded=bool(artifacts)):
            if not artifacts:
                st.info("No versions yet.")
                continue
            st.dataframe(artifacts, use_container_width=True, hide_index=True)
            version_options = [artifact["version"] for artifact in artifacts]
            default_index = version_options.index(current) if current in version_options else 0
            selected_version = st.selectbox(
                f"Active {STEP_LABELS[step]} Version",
                options=version_options,
                index=default_index,
                key=f"select-{item_id}-{step}",
            )
            if st.button(
                f"Use {selected_version}",
                key=f"use-version-{item_id}-{step}",
                use_container_width=True,
            ):
                try:
                    set_current_version(task_id, item_id, step, selected_version)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Switched {step} to {selected_version}.")
                    _rerun()


def _render_manual_edits(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    brief_artifact = _artifact_or_none(
        task_id,
        item_id,
        STEP_BRIEF_GENERATION,
        item["current_versions"].get("brief_generation"),
    )
    prompt_artifact = _artifact_or_none(
        task_id,
        item_id,
        STEP_IMAGE_PROMPT,
        item["current_versions"].get("image_prompt"),
    )

    left, right = st.columns(2)
    with left:
        st.markdown("### Edit Brief")
        with st.form(f"edit-brief-form-{item_id}"):
            brief_output = brief_artifact.get("output", {}) if brief_artifact else {}
            title = st.text_input("Title", value=brief_output.get("title", item.get("title", "")))
            description = st.text_area(
                "Description",
                value=brief_output.get("description", item.get("description", "")),
                height=120,
            )
            keywords = st.text_input(
                "Keywords (comma separated)",
                value=", ".join(brief_output.get("keywords", [])),
            )
            visual_focus = st.text_input(
                "Visual Focus",
                value=brief_output.get("visual_focus", ""),
            )
            note = st.text_input("Note", value="manual brief edit")
            submitted = st.form_submit_button("Save Brief Version", use_container_width=True)
        if submitted:
            try:
                edit_brief(
                    task_id,
                    item_id,
                    title=title,
                    description=description,
                    keywords=[keyword.strip() for keyword in keywords.split(",") if keyword.strip()],
                    visual_focus=visual_focus,
                    note=note,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Manual brief version saved.")
                _rerun()
        if st.button("Rollback To Brief", key=f"rollback-brief-{item_id}", use_container_width=True):
            try:
                rollback_step(task_id, item_id, STEP_BRIEF_GENERATION)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Rolled back to brief stage.")
                _rerun()

    with right:
        st.markdown("### Edit Prompt")
        with st.form(f"edit-prompt-form-{item_id}"):
            prompt_output = prompt_artifact.get("output", {}) if prompt_artifact else {}
            prompt_text = st.text_area(
                "Prompt",
                value=prompt_output.get("prompt", ""),
                height=140,
            )
            negative_prompt = st.text_area(
                "Negative Prompt",
                value=prompt_output.get("negative_prompt", ""),
                height=100,
            )
            note = st.text_input("Prompt Note", value="manual prompt edit")
            submitted = st.form_submit_button("Save Prompt Version", use_container_width=True)
        if submitted:
            try:
                edit_prompt(
                    task_id,
                    item_id,
                    prompt=prompt_text,
                    negative_prompt=negative_prompt,
                    note=note,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Manual prompt version saved.")
                _rerun()
        if st.button("Rollback To Prompt", key=f"rollback-prompt-{item_id}", use_container_width=True):
            try:
                rollback_step(task_id, item_id, STEP_IMAGE_PROMPT)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Rolled back to prompt stage.")
                _rerun()


def _render_events(task_id: str, item_id: str) -> None:
    task_events, item_events = st.tabs(["Task Events", "Item Events"])
    with task_events:
        _show_json(load_task_events(task_id))
    with item_events:
        _show_json(load_item_events(task_id, item_id))


def _render_item_workspace(task_id: str, item: dict) -> None:
    st.markdown(
        f"""
        <div class="panel">
          <div class="kicker">Selected Item</div>
          <h3 style="margin:0.15rem 0 0.25rem 0;">{item.get('title') or item['item_id']}</h3>
          <p style="margin:0;color:#475569;">{item.get('asset_type')} · {item.get('category') or 'uncategorized'} · {item.get('status')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_action_bar(task_id, item)
    current_tab, versions_tab, edits_tab, events_tab = st.tabs(
        ["Current Output", "Versions", "Manual Edits", "Events"]
    )
    with current_tab:
        _render_current_outputs(task_id, item)
    with versions_tab:
        _render_versions(task_id, item)
    with edits_tab:
        _render_manual_edits(task_id, item)
    with events_tab:
        _render_events(task_id, item["item_id"])


def main() -> None:
    st.set_page_config(
        page_title="AI Icon Pipeline Workspace",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()
    st.markdown('<div class="app-shell">', unsafe_allow_html=True)
    tasks = list_tasks()
    selected_task_id = _render_sidebar(tasks)

    if not selected_task_id:
        st.markdown(
            """
            <div class="hero">
              <div class="kicker">No Tasks Yet</div>
              <h1>Start With A Batch</h1>
              <p>Create a task from the sidebar and the workspace will appear here.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    task = load_task(selected_task_id)
    items = list_items(selected_task_id)
    _render_task_summary(task, items)

    if not items:
        st.warning("This task has no items.")
        st.stop()

    item_lookup = {item["item_id"]: item for item in items}
    current_item_id = st.selectbox(
        "Selected Item",
        options=[item["item_id"] for item in items],
        format_func=lambda item_id: _item_label(item_lookup[item_id]),
        key=f"selected-item-{selected_task_id}",
    )
    _render_item_workspace(selected_task_id, item_lookup[current_item_id])
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
