"""
Unit tests for commit parser utilities.

Tests parsing miner commitments from the subnet commit payload.
"""

import json


class TestParseCommit:
    """Tests for the parse_commit helper."""

    def test_parse_commit_valid_json(self):
        """Test parsing valid JSON commitment with all required fields."""
        from leoma.infra.commit_parser import parse_commit

        commit_value = json.dumps({
            "model_name": "user/leoma-video-model",
            "model_revision": "abc123def456",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        })
        result = parse_commit(commit_value)

        assert result["model_name"] == "user/leoma-video-model"
        assert result["model_revision"] == "abc123def456"
        assert result["chute_id"] == "3182321e-3e58-55da-ba44-051686ddbfe5"

    def test_parse_commit_json_with_extra_fields(self):
        """Test parsing JSON with additional fields."""
        from leoma.infra.commit_parser import parse_commit

        commit_value = json.dumps({
            "model_name": "user/model",
            "model_revision": "abc123",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
            "version": "1.0",
            "metadata": {"key": "value"},
        })
        result = parse_commit(commit_value)

        assert result["model_name"] == "user/model"
        assert result["model_revision"] == "abc123"
        assert result["chute_id"] == "3182321e-3e58-55da-ba44-051686ddbfe5"
        assert result["version"] == "1.0"
        assert result["metadata"] == {"key": "value"}

    def test_parse_commit_plain_string(self):
        """Test parsing plain string commitment (not JSON) returns empty dict."""
        from leoma.infra.commit_parser import parse_commit

        commit_value = "3182321e-3e58-55da-ba44-051686ddbfe5"
        result = parse_commit(commit_value)

        # Non-JSON strings return empty dict
        assert result == {}

    def test_parse_commit_empty_string(self):
        """Test parsing empty string commitment."""
        from leoma.infra.commit_parser import parse_commit

        result = parse_commit("")

        assert result == {}

    def test_parse_commit_none(self):
        """Test parsing None commitment."""
        from leoma.infra.commit_parser import parse_commit

        result = parse_commit(None)

        assert result == {}

    def test_parse_commit_invalid_json(self):
        """Test parsing invalid JSON returns empty dict."""
        from leoma.infra.commit_parser import parse_commit

        commit_value = "{invalid json}"
        result = parse_commit(commit_value)

        assert result == {}

    def test_parse_commit_json_array(self):
        """Test that JSON array returns empty dict (not a dict)."""
        from leoma.infra.commit_parser import parse_commit

        commit_value = json.dumps(["not", "a", "dict"])
        result = parse_commit(commit_value)

        # Arrays are not dicts, so return empty
        assert result == {}

    def test_parse_commit_json_number(self):
        """Test that JSON number returns empty dict."""
        from leoma.infra.commit_parser import parse_commit

        commit_value = "12345"
        result = parse_commit(commit_value)

        assert result == {}

    def test_parse_commit_empty_json_object(self):
        """Test parsing empty JSON object."""
        from leoma.infra.commit_parser import parse_commit

        commit_value = json.dumps({})
        result = parse_commit(commit_value)

        assert result == {}

    def test_parse_commit_json_boolean(self):
        """Test that JSON boolean returns empty dict."""
        from leoma.infra.commit_parser import parse_commit

        result = parse_commit("true")
        assert result == {}

    def test_parse_commit_nested_json(self):
        """Test parsing deeply nested JSON."""
        from leoma.infra.commit_parser import parse_commit

        commit_value = json.dumps({
            "model_name": "user/model",
            "model_revision": "abc123",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
            "config": {
                "nested": {
                    "deep": "value",
                },
            },
        })
        result = parse_commit(commit_value)

        assert result["model_name"] == "user/model"
        assert result["chute_id"] == "3182321e-3e58-55da-ba44-051686ddbfe5"
        assert result["config"]["nested"]["deep"] == "value"


class TestCommitmentValidation:
    """Tests for commitment validation logic."""

    def test_validate_commit_fields_all_present(self):
        """Test validation passes when repo name (after '/') starts with leoma."""
        from leoma.infra.commit_parser import validate_commit_fields

        commit = {
            "model_name": "your_username/leoma-video-model",
            "model_revision": "abc123def456",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        }
        is_valid, reason = validate_commit_fields(commit)
        assert is_valid is True
        assert reason is None

    def test_validate_commit_fields_missing_model_name(self):
        """Test validation fails when model_name is missing."""
        from leoma.infra.commit_parser import validate_commit_fields

        commit = {
            "model_revision": "abc123",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        }
        is_valid, reason = validate_commit_fields(commit)

        assert is_valid is False
        assert reason == "missing_model_name"

    def test_validate_commit_fields_missing_model_revision(self):
        """Test validation fails when model_revision is missing."""
        from leoma.infra.commit_parser import validate_commit_fields

        commit = {
            "model_name": "user/leoma-video-model",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        }
        is_valid, reason = validate_commit_fields(commit)
        assert is_valid is False
        assert reason == "missing_model_revision"

    def test_validate_commit_fields_missing_chute_id(self):
        """Test validation fails when chute_id is missing."""
        from leoma.infra.commit_parser import validate_commit_fields

        commit = {
            "model_name": "user/leoma-video-model",
            "model_revision": "abc123",
        }
        is_valid, reason = validate_commit_fields(commit)
        assert is_valid is False
        assert reason == "missing_chute_id"

    def test_validate_commit_fields_empty_values(self):
        """Test validation fails with empty string values."""
        from leoma.infra.commit_parser import validate_commit_fields

        commit = {
            "model_name": "",
            "model_revision": "abc123",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        }
        is_valid, reason = validate_commit_fields(commit)

        assert is_valid is False
        assert reason == "missing_model_name"

    def test_valid_chute_id_uuid_format(self):
        """Test validation of chute_id UUID format."""
        from leoma.infra.commit_parser import parse_commit

        valid_chute_ids = [
            "3182321e-3e58-55da-ba44-051686ddbfe5",
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "00000000-0000-0000-0000-000000000000",
        ]
        for chute_id in valid_chute_ids:
            result = parse_commit(json.dumps({
                "model_name": "user/leoma-video-model",
                "model_revision": "abc123",
                "chute_id": chute_id,
            }))
            assert result["chute_id"] == chute_id

    def test_valid_model_name_formats(self):
        """Repo name (after '/') must start with leoma; username is excluded (case-insensitive)."""
        from leoma.infra.commit_parser import parse_commit, validate_commit_fields

        valid_model_names = [
            "your_username/leoma-video-model",
            "org/leoma-video",
            "user/LEOMA-transformers",
            "a/Leoma-my-model",
        ]
        for model_name in valid_model_names:
            commit = {
                "model_name": model_name,
                "model_revision": "abc123",
                "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
            }
            result = parse_commit(json.dumps(commit))
            is_valid, _ = validate_commit_fields(result)
            assert is_valid is True, f"expected valid: {model_name!r}"
            assert result["model_name"] == model_name

    def test_validate_commit_fields_model_name_must_start_with_leoma(self):
        """Test validation fails when repo name (after '/') does not start with leoma."""
        from leoma.infra.commit_parser import validate_commit_fields

        commit = {
            "model_name": "user/model",
            "model_revision": "abc123",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        }
        is_valid, reason = validate_commit_fields(commit)
        assert is_valid is False
        assert reason == "model_name_must_start_with_leoma"

    def test_validate_commit_fields_model_name_must_end_with_hotkey(self):
        """Test validation fails when repo name does not end with hotkey (when hotkey provided)."""
        from leoma.infra.commit_parser import validate_commit_fields

        hotkey = "5D9KxqM4nTa8cJrL2WvY6hP3sFzU1bN7eQmR5tHkC8yLpXaZ"
        commit = {
            "model_name": "user/leoma-video-model",
            "model_revision": "abc123",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        }
        is_valid, reason = validate_commit_fields(commit, hotkey=hotkey)
        assert is_valid is False
        assert reason == "model_name_must_end_with_hotkey"

    def test_validate_commit_fields_model_name_ends_with_hotkey_case_insensitive(self):
        """Repo name must end with hotkey; comparison is case-insensitive; username excluded."""
        from leoma.infra.commit_parser import validate_commit_fields

        hotkey = "5D9KxqM4nTa8cJrL2WvY6hP3sFzU1bN7eQmR5tHkC8yLpXaZ"
        # Hugging Face style: username/leoma-hh-<hotkey>
        commit = {
            "model_name": f"your_username/leoma-hh-{hotkey}",
            "model_revision": "abc123",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        }
        is_valid, reason = validate_commit_fields(commit, hotkey=hotkey)
        assert is_valid is True, reason
        assert reason is None
        # Uppercase hotkey in repo name still matches
        commit_upper = {
            "model_name": "user/leoma-hh-5D9KXQM4NTA8CJRL2WVY6HP3SFZU1BN7EQMR5THKC8YLPXAZ",
            "model_revision": "abc123",
            "chute_id": "3182321e-3e58-55da-ba44-051686ddbfe5",
        }
        is_valid2, reason2 = validate_commit_fields(commit_upper, hotkey=hotkey)
        assert is_valid2 is True, reason2
        assert reason2 is None

    def test_empty_commitment_handling(self):
        """Test handling of various empty commitments."""
        from leoma.infra.commit_parser import parse_commit

        # These should all return empty dict
        assert parse_commit(None) == {}
        assert parse_commit("") == {}
        assert parse_commit(json.dumps({})) == {}
        assert parse_commit("   ") == {}
