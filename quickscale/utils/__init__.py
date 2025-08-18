# Expose utility functions from various modules
from .template_generator import (
    copy_sync_modules,
    fix_imports,
    process_file_templates,
    render_template,
    is_binary_file,
    remove_duplicated_templates
)
from .message_manager import MessageManager, MessageType