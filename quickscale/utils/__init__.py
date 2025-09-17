# Expose utility functions from various modules
from .message_manager import MessageManager, MessageType
from .template_generator import (
    copy_sync_modules,
    fix_imports,
    is_binary_file,
    process_file_templates,
    remove_duplicated_templates,
    render_template,
)

__all__ = [
    'copy_sync_modules',
    'fix_imports',
    'process_file_templates',
    'render_template',
    'is_binary_file',
    'remove_duplicated_templates',
    'MessageManager',
    'MessageType',
]
