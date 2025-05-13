"""Unit tests for the color and icon functionality of MessageManager."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

from quickscale.utils.message_manager import MessageManager, MessageType


@pytest.fixture
def mock_stdout_tty():
    """Mock sys.stdout as a TTY."""
    with patch('sys.stdout.isatty', return_value=True):
        yield


@pytest.fixture
def mock_stdout_not_tty():
    """Mock sys.stdout as not a TTY."""
    with patch('sys.stdout.isatty', return_value=False):
        yield


class TestMessageManagerColorAndIcons:
    """Test the color and icon functionality of MessageManager."""
    
    def test_use_color_with_tty(self, mock_stdout_tty):
        """Test that _use_color returns True when stdout is a TTY and NO_COLOR is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert MessageManager._use_color() is True
    
    def test_use_color_without_tty(self, mock_stdout_not_tty):
        """Test that _use_color returns False when stdout is not a TTY."""
        with patch.dict(os.environ, {}, clear=True):
            assert MessageManager._use_color() is False
    
    def test_use_color_respects_no_color_env(self, mock_stdout_tty):
        """Test that _use_color respects NO_COLOR environment variable."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}, clear=True):
            assert MessageManager._use_color() is False
    
    def test_use_icons_default(self):
        """Test that _use_icons returns True by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert MessageManager._use_icons() is True
    
    def test_use_icons_respects_no_icons_env(self):
        """Test that _use_icons respects QUICKSCALE_NO_ICONS environment variable."""
        with patch.dict(os.environ, {"QUICKSCALE_NO_ICONS": "1"}, clear=True):
            assert MessageManager._use_icons() is False
    
    def test_format_message_with_color_and_icon(self, mock_stdout_tty):
        """Test that _format_message includes color and icon when both are enabled."""
        with patch.object(MessageManager, '_use_color', return_value=True), \
             patch.object(MessageManager, '_use_icons', return_value=True):
            message = "Test message"
            result = MessageManager._format_message(message, MessageType.SUCCESS)
            # Check that both color code and icon are present
            assert MessageManager.COLORS[MessageManager.TYPE_COLORS[MessageType.SUCCESS]] in result
            assert MessageManager.ICONS[MessageType.SUCCESS] in result
            assert message in result
            assert MessageManager.COLORS["reset"] in result
    
    def test_format_message_with_color_without_icon(self, mock_stdout_tty):
        """Test that _format_message includes color but not icon when icons are disabled."""
        with patch.object(MessageManager, '_use_color', return_value=True), \
             patch.object(MessageManager, '_use_icons', return_value=False):
            message = "Test message"
            result = MessageManager._format_message(message, MessageType.SUCCESS, use_icon=True)
            # Check that color code is present but icon is not
            assert MessageManager.COLORS[MessageManager.TYPE_COLORS[MessageType.SUCCESS]] in result
            assert MessageManager.ICONS[MessageType.SUCCESS] not in result
            assert message in result
            assert MessageManager.COLORS["reset"] in result
    
    def test_format_message_without_color_with_icon(self, mock_stdout_not_tty):
        """Test that _format_message includes icon but not color when color is disabled."""
        with patch.object(MessageManager, '_use_color', return_value=False), \
             patch.object(MessageManager, '_use_icons', return_value=True):
            message = "Test message"
            result = MessageManager._format_message(message, MessageType.SUCCESS)
            # Check that icon is present but color code is not
            assert MessageManager.COLORS[MessageManager.TYPE_COLORS[MessageType.SUCCESS]] not in result
            assert MessageManager.ICONS[MessageType.SUCCESS] in result
            assert message in result
            assert MessageManager.COLORS["reset"] not in result
    
    def test_format_message_without_color_without_icon(self, mock_stdout_not_tty):
        """Test that _format_message includes neither color nor icon when both are disabled."""
        with patch.object(MessageManager, '_use_color', return_value=False), \
             patch.object(MessageManager, '_use_icons', return_value=False):
            message = "Test message"
            result = MessageManager._format_message(message, MessageType.SUCCESS)
            # Check that neither color code nor icon is present
            assert MessageManager.COLORS[MessageManager.TYPE_COLORS[MessageType.SUCCESS]] not in result
            assert MessageManager.ICONS[MessageType.SUCCESS] not in result
            assert message in result
            assert MessageManager.COLORS["reset"] not in result
