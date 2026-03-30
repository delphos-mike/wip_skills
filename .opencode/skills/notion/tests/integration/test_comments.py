"""Integration tests: page-level comments, block-level comments, replies, extraction."""

from create_comment import create_comment
from helpers import append_blocks, get_top_blocks
from notion_utils import (
    api_call,
    markdown_to_blocks,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _get_comments_for(api_key: str, block_id: str) -> list:
    """Fetch comments attached to a block (or page-level if block_id is page)."""
    resp = api_call(f"comments?block_id={block_id}", api_key)
    return resp.get("results", [])


def _comment_text(comment: dict) -> str:
    return "".join(rt.get("plain_text", "") for rt in comment.get("rich_text", []))


def _write_content(api_key, page_id):  # noqa: ANN202
    """Write two paragraphs to the test page, return their block objects."""
    md = """\
This is paragraph one for comment testing.

This is paragraph two for comment testing."""
    blocks = markdown_to_blocks(md)
    append_blocks(api_key, page_id, blocks)
    remote = get_top_blocks(api_key, page_id)
    paras = [b for b in remote if b["type"] == "paragraph"]
    assert len(paras) >= 2, f"Expected 2 paragraphs, got {len(paras)}"
    return paras


# ── Tests ────────────────────────────────────────────────────────────


class TestPageLevelComments:
    def test_create_page_comment(self, api_key, page_id):
        result = create_comment(
            api_key,
            "Integration test: page-level comment",
            page_id=page_id,
        )
        assert result.get("object") != "error", result.get("message")
        assert result["parent"]["type"] == "page_id"
        assert "id" in result
        assert "discussion_id" in result

    def test_page_comment_with_formatting(self, api_key, page_id):
        result = create_comment(
            api_key,
            "Comment with **bold** and `code` and [a link](https://example.com)",
            page_id=page_id,
        )
        assert result.get("object") != "error", result.get("message")

        # Verify formatting is in the rich_text
        rt_items = result.get("rich_text", [])
        annotations = {}
        for item in rt_items:
            text = item.get("plain_text", "")
            annot = item.get("annotations", {})
            if annot.get("bold"):
                annotations["bold"] = text
            if annot.get("code"):
                annotations["code"] = text

        assert "bold" in annotations
        assert "code" in annotations

    def test_page_comment_retrievable(self, api_key, page_id):
        create_comment(
            api_key,
            "Retrievable page comment",
            page_id=page_id,
        )

        comments = _get_comments_for(api_key, page_id)
        texts = [_comment_text(c) for c in comments]
        assert any("Retrievable page comment" in t for t in texts)


class TestBlockLevelComments:
    def test_create_block_comment(self, api_key, page_id):
        paras = _write_content(api_key, page_id)
        block_id = paras[0]["id"]

        result = create_comment(
            api_key,
            "Block-level comment on paragraph one",
            block_id=block_id,
        )
        assert result.get("object") != "error", result.get("message")
        assert result["parent"]["type"] == "block_id"

    def test_block_comment_attached_to_correct_block(self, api_key, page_id):
        paras = _write_content(api_key, page_id)
        block_id_1 = paras[0]["id"]
        block_id_2 = paras[1]["id"]

        create_comment(api_key, "Comment for block 1", block_id=block_id_1)
        create_comment(api_key, "Comment for block 2", block_id=block_id_2)

        comments_1 = _get_comments_for(api_key, block_id_1)
        comments_2 = _get_comments_for(api_key, block_id_2)

        texts_1 = [_comment_text(c) for c in comments_1]
        texts_2 = [_comment_text(c) for c in comments_2]

        assert any("block 1" in t for t in texts_1)
        assert any("block 2" in t for t in texts_2)
        # And NOT cross-contaminated
        assert not any("block 2" in t for t in texts_1)
        assert not any("block 1" in t for t in texts_2)


class TestCommentReplies:
    def test_reply_to_discussion(self, api_key, page_id):
        # Create initial comment
        initial = create_comment(
            api_key,
            "Thread starter",
            page_id=page_id,
        )
        disc_id = initial["discussion_id"]

        # Reply to the thread
        reply = create_comment(
            api_key,
            "Reply in thread",
            discussion_id=disc_id,
        )
        assert reply.get("object") != "error", reply.get("message")
        assert reply["discussion_id"] == disc_id

    def test_multiple_replies_same_thread(self, api_key, page_id):
        initial = create_comment(api_key, "Multi-reply starter", page_id=page_id)
        disc_id = initial["discussion_id"]

        for i in range(3):
            reply = create_comment(api_key, f"Reply {i + 1}", discussion_id=disc_id)
            assert reply.get("object") != "error"
            assert reply["discussion_id"] == disc_id

    def test_reply_to_block_comment_thread(self, api_key, page_id):
        paras = _write_content(api_key, page_id)
        block_id = paras[0]["id"]

        initial = create_comment(api_key, "Block thread starter", block_id=block_id)
        disc_id = initial["discussion_id"]

        reply = create_comment(api_key, "Reply to block thread", discussion_id=disc_id)
        assert reply.get("object") != "error"
        assert reply["discussion_id"] == disc_id

        # Verify both appear when fetching block comments
        comments = _get_comments_for(api_key, block_id)
        texts = [_comment_text(c) for c in comments]
        assert any("Block thread starter" in t for t in texts)
        assert any("Reply to block thread" in t for t in texts)
