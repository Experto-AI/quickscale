"""Unit tests for CommandManager."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from quickscale.commands.command_manager import CommandManager
from quickscale.commands.command_base import Command
from quickscale.utils.error_manager import CommandError


class MockCommand(Command):
    """Mock command for testing."""
    
    def __init__(self, return_value: Any = None, should_raise: Exception = None):
        """Initialize mock command."""
        super().__init__()
        self.return_value = return_value
        self.should_raise = should_raise
        self.call_count = 0
        self.last_args = None
        self.last_kwargs = None
    
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute mock command."""
        self.call_count += 1
        self.last_args = args
        self.last_kwargs = kwargs
        
        if self.should_raise:
            raise self.should_raise
        
        return self.return_value


class TestCommandManager:
    """Tests for CommandManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command_manager = CommandManager()
    
    def test_initialization(self):
        """Test CommandManager initialization creates all commands."""
        expected_commands = {
            'init', 'destroy', 'up', 'down', 'logs', 'ps',
            'shell', 'django-shell', 'manage', 'check',
            'generate-service', 'validate-service', 'show-service-examples',
            'sync-back', 'help', 'version'
        }
        
        assert set(self.command_manager._commands.keys()) == expected_commands
    
    def test_get_available_commands(self):
        """Test getting list of available commands."""
        commands = self.command_manager.get_available_commands()
        assert isinstance(commands, list)
        assert 'init' in commands
        assert 'up' in commands
        assert 'check' in commands
    
    def test_execute_command_success(self):
        """Test successful command execution."""
        mock_command = MockCommand(return_value="test_result")
        self.command_manager._commands['test'] = mock_command
        
        result = self.command_manager.execute_command('test', 'arg1', 'arg2', key='value')
        
        assert result == "test_result"
        assert mock_command.call_count == 1
        assert mock_command.last_args == ('arg1', 'arg2')
        assert mock_command.last_kwargs == {'key': 'value'}
    
    def test_execute_command_not_found(self):
        """Test executing non-existent command."""
        with pytest.raises(KeyError, match="Command 'nonexistent' not found"):
            self.command_manager.execute_command('nonexistent')
    
    def test_execute_command_destroy_special_handling(self):
        """Test special handling for destroy command with delete_images."""
        mock_command = MockCommand()
        self.command_manager._commands['destroy'] = mock_command
        
        self.command_manager.execute_command('destroy', delete_images=True)
        
        assert mock_command.call_count == 1
        assert mock_command.last_kwargs == {'delete_images': True}
    
    @patch('quickscale.commands.command_manager.InitCommand')
    def test_init_project(self, mock_init_command):
        """Test project initialization."""
        mock_instance = Mock()
        mock_init_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.init_project('test_project')
        
        mock_instance.execute.assert_called_once_with('test_project')
    
    @patch('quickscale.commands.command_manager.DestroyProjectCommand')
    def test_destroy_project(self, mock_destroy_command):
        """Test project destruction."""
        mock_instance = Mock()
        mock_instance.execute.return_value = {'success': True}
        mock_destroy_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        result = command_manager.destroy_project()
        
        mock_instance.execute.assert_called_once()
        assert result == {'success': True}
    
    @patch('quickscale.commands.command_manager.ServiceUpCommand')
    def test_start_services(self, mock_up_command):
        """Test starting services."""
        mock_instance = Mock()
        mock_up_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.start_services()
        
        mock_instance.execute.assert_called_once()
    
    @patch('quickscale.commands.command_manager.ServiceDownCommand')
    def test_stop_services(self, mock_down_command):
        """Test stopping services."""
        mock_instance = Mock()
        mock_down_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.stop_services()
        
        mock_instance.execute.assert_called_once()
    
    @patch('quickscale.commands.command_manager.ServiceLogsCommand')
    def test_view_logs(self, mock_logs_command):
        """Test viewing logs with various parameters."""
        mock_instance = Mock()
        mock_logs_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.view_logs(
            service='web',
            follow=True,
            since='1h',
            lines=50,
            timestamps=True
        )
        
        mock_instance.execute.assert_called_once_with(
            'web', follow=True, since='1h', lines=50, timestamps=True
        )
    
    @patch('quickscale.commands.command_manager.ServiceStatusCommand')
    def test_check_services_status(self, mock_status_command):
        """Test checking services status."""
        mock_instance = Mock()
        mock_status_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.check_services_status()
        
        mock_instance.execute.assert_called_once()
    
    @patch('quickscale.commands.command_manager.ShellCommand')
    def test_open_shell(self, mock_shell_command):
        """Test opening shell."""
        mock_instance = Mock()
        mock_shell_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.open_shell(command='ls -la')
        
        mock_instance.execute.assert_called_once_with(command='ls -la')
    
    @patch('quickscale.commands.command_manager.DjangoShellCommand')
    def test_open_django_shell(self, mock_django_shell_command):
        """Test opening Django shell."""
        mock_instance = Mock()
        mock_django_shell_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.open_shell(django_shell=True)
        
        mock_instance.execute.assert_called_once()
    
    @patch('quickscale.commands.command_manager.ManageCommand')
    def test_run_manage_command(self, mock_manage_command):
        """Test running Django management command."""
        mock_instance = Mock()
        mock_manage_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.run_manage_command(['migrate', '--fake'])
        
        mock_instance.execute.assert_called_once_with(['migrate', '--fake'])
    
    @patch('quickscale.commands.command_manager.CheckCommand')
    def test_check_requirements(self, mock_check_command):
        """Test checking requirements."""
        mock_instance = Mock()
        mock_check_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.check_requirements(print_info=False)
        
        mock_instance.execute.assert_called_once_with(print_info=False)
    
    @patch('quickscale.commands.command_manager.SyncBackCommand')
    def test_sync_back_project(self, mock_sync_command):
        """Test sync back project."""
        mock_instance = Mock()
        mock_sync_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        command_manager.sync_back_project(
            project_path='/path/to/project',
            preview=True,
            apply=False,
            interactive=True
        )
        
        mock_instance.execute.assert_called_once_with(
            '/path/to/project', preview=True, apply=False, interactive=True
        )
    
    @patch('quickscale.commands.command_manager.ServiceGeneratorCommand')
    def test_generate_service(self, mock_generator_command):
        """Test service generation."""
        mock_instance = Mock()
        mock_instance.execute.return_value = {'success': True, 'file': 'test_service.py'}
        mock_generator_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        result = command_manager.generate_service(
            service_name='test_service',
            service_type='text_processing',
            output_dir='/custom/dir',
            credit_cost=2.5,
            description='Test service',
            skip_db_config=True,
            free=False
        )
        
        mock_instance.execute.assert_called_once_with(
            'test_service',
            service_type='text_processing',
            output_dir='/custom/dir',
            credit_cost=2.5,
            description='Test service',
            skip_db_config=True,
            free=False
        )
        assert result == {'success': True, 'file': 'test_service.py'}
    
    @patch('quickscale.commands.command_manager.ValidateServiceCommand')
    def test_validate_service(self, mock_validate_command):
        """Test service validation."""
        mock_instance = Mock()
        mock_instance.execute.return_value = {'valid': True, 'issues': []}
        mock_validate_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        result = command_manager.validate_service('test_service.py', show_tips=True)
        
        mock_instance.execute.assert_called_once_with('test_service.py', show_tips=True)
        assert result == {'valid': True, 'issues': []}
    
    @patch('quickscale.commands.command_manager.ServiceExamplesCommand')
    def test_show_service_examples(self, mock_examples_command):
        """Test showing service examples."""
        mock_instance = Mock()
        mock_instance.execute.return_value = {'examples': ['example1', 'example2']}
        mock_examples_command.return_value = mock_instance
        
        # Reinitialize to use the mocked command
        command_manager = CommandManager()
        result = command_manager.show_service_examples(example_type='text_processing')
        
        mock_instance.execute.assert_called_once_with(example_type='text_processing')
        assert result == {'examples': ['example1', 'example2']}
    
    def test_handle_service_commands(self):
        """Test handling service commands."""
        # Mock the command methods
        with patch.object(self.command_manager, 'start_services') as mock_start:
            result = self.command_manager._handle_service_commands('up', Mock())
            mock_start.assert_called_once()
        
        with patch.object(self.command_manager, 'stop_services') as mock_stop:
            result = self.command_manager._handle_service_commands('down', Mock())
            mock_stop.assert_called_once()
        
        # Test logs command
        args = Mock()
        args.service = 'web'
        args.follow = True
        args.since = '1h'
        args.lines = 50
        args.timestamps = True
        
        with patch.object(self.command_manager, 'view_logs') as mock_logs:
            result = self.command_manager._handle_service_commands('logs', args)
            mock_logs.assert_called_once_with(
                service='web', follow=True, since='1h', lines=50, timestamps=True
            )
        
        with patch.object(self.command_manager, 'check_services_status') as mock_status:
            result = self.command_manager._handle_service_commands('ps', Mock())
            mock_status.assert_called_once()
        
        # Test unknown service command
        result = self.command_manager._handle_service_commands('unknown', Mock())
        assert result is None
    
    def test_handle_project_commands(self):
        """Test handling project commands."""
        args = Mock()
        args.name = 'test_project'
        
        with patch.object(self.command_manager, 'init_project') as mock_init:
            result = self.command_manager._handle_project_commands('init', args)
            mock_init.assert_called_once_with('test_project')
        
        with patch.object(self.command_manager, 'destroy_project') as mock_destroy:
            result = self.command_manager._handle_project_commands('destroy', Mock())
            mock_destroy.assert_called_once()
        
        with patch.object(self.command_manager, 'check_requirements') as mock_check:
            result = self.command_manager._handle_project_commands('check', Mock())
            mock_check.assert_called_once_with(print_info=True)
        
        # Test unknown project command
        result = self.command_manager._handle_project_commands('unknown', Mock())
        assert result is None
    
    def test_handle_shell_commands(self):
        """Test handling shell commands."""
        # Test shell command
        args = Mock()
        args.cmd = 'ls -la'
        
        with patch.object(self.command_manager, 'open_shell') as mock_shell:
            result = self.command_manager._handle_shell_commands('shell', args)
            mock_shell.assert_called_once_with(command='ls -la')
        
        # Test django-shell command
        with patch.object(self.command_manager, 'execute_command') as mock_execute:
            result = self.command_manager._handle_shell_commands('django-shell', Mock())
            mock_execute.assert_called_once_with('django-shell')
        
        # Test manage command
        args = Mock()
        args.args = ['migrate', '--fake']
        
        with patch.object(self.command_manager, 'run_manage_command') as mock_manage:
            result = self.command_manager._handle_shell_commands('manage', args)
            mock_manage.assert_called_once_with(['migrate', '--fake'])
        
        # Test unknown shell command
        result = self.command_manager._handle_shell_commands('unknown', Mock())
        assert result is None
    
    def test_handle_development_commands(self):
        """Test handling development commands."""
        args = Mock()
        args.project_path = '/path/to/project'
        args.preview = True
        args.apply = False
        args.interactive = True
        
        with patch.object(self.command_manager, 'sync_back_project') as mock_sync:
            result = self.command_manager._handle_development_commands('sync-back', args)
            mock_sync.assert_called_once_with(
                project_path='/path/to/project',
                preview=True,
                apply=False,
                interactive=True
            )
        
        # Test unknown development command
        result = self.command_manager._handle_development_commands('unknown', Mock())
        assert result is None
    
    def test_handle_service_generator_commands(self):
        """Test handling service generator commands."""
        # Test generate-service command
        args = Mock()
        args.name = 'test_service'
        args.type = 'text_processing'
        args.output_dir = '/custom/dir'
        args.credit_cost = 2.5
        args.description = 'Test service'
        args.skip_db_config = True
        args.free = False
        
        with patch.object(self.command_manager, 'generate_service') as mock_generate:
            result = self.command_manager._handle_service_generator_commands('generate-service', args)
            mock_generate.assert_called_once_with(
                service_name='test_service',
                service_type='text_processing',
                output_dir='/custom/dir',
                credit_cost=2.5,
                description='Test service',
                skip_db_config=True,
                free=False
            )
        
        # Test validate-service command
        args = Mock()
        args.name_or_path = 'test_service.py'
        args.tips = True
        
        with patch.object(self.command_manager, 'execute_command') as mock_execute:
            result = self.command_manager._handle_service_generator_commands('validate-service', args)
            mock_execute.assert_called_once_with(
                'validate-service',
                name_or_path='test_service.py',
                show_tips=True
            )
        
        # Test show-service-examples command
        args = Mock()
        args.type = 'text_processing'
        
        with patch.object(self.command_manager, 'show_service_examples') as mock_examples:
            result = self.command_manager._handle_service_generator_commands('show-service-examples', args)
            mock_examples.assert_called_once_with(example_type='text_processing')
        
        # Test unknown generator command
        result = self.command_manager._handle_service_generator_commands('unknown', Mock())
        assert result is None
    
    @patch('quickscale.utils.message_manager.MessageManager.info')
    def test_display_help_general(self, mock_info):
        """Test displaying general help."""
        self.command_manager._display_help()
        
        # Check that info was called multiple times
        assert mock_info.called
        
        # Check that usage and command information was displayed
        call_messages = [call[0][0] for call in mock_info.call_args_list]
        
        assert any("usage:" in msg.lower() for msg in call_messages)
        assert any("init" in msg for msg in call_messages)
        assert any("up" in msg for msg in call_messages)
        assert any("help" in msg for msg in call_messages)
    
    @patch('quickscale.utils.help_manager.show_manage_help')
    def test_display_help_manage(self, mock_show_manage_help):
        """Test displaying manage help."""
        self.command_manager._display_help('manage')
        
        mock_show_manage_help.assert_called_once()
    
    @patch('quickscale.utils.message_manager.MessageManager.info')
    def test_handle_info_commands(self, mock_info):
        """Test handling info commands."""
        # Test help command
        with patch.object(self.command_manager, '_display_help') as mock_display_help:
            result = self.command_manager._handle_info_commands('help', Mock())
            mock_display_help.assert_called_once()
            assert result is None  # Method returns None for help
        
        # Test version command
        with patch('quickscale.__version__', '1.0.0'):
            result = self.command_manager._handle_info_commands('version', Mock())
            mock_info.assert_called_with("QuickScale version 1.0.0")
            assert result is None  # Method returns None for version
        
        # Test unknown info command
        result = self.command_manager._handle_info_commands('unknown', Mock())
        assert result is None
        assert result is None
    
    def test_handle_command_dispatch(self):
        """Test command dispatching through handle_command."""
        args = Mock()
        args.name = 'test_project'
        
        # Test successful command dispatch
        with patch.object(self.command_manager, '_handle_project_commands', return_value='success'):
            result = self.command_manager.handle_command('init', args)
            assert result == 'success'
        
        # Test command not found
        with pytest.raises(KeyError, match="Command 'nonexistent' not found"):
            self.command_manager.handle_command('nonexistent', args)
        
        # Test when no handler handles the command (should not happen in practice)
        with patch.object(self.command_manager, '_handle_service_commands', return_value=None):
            with patch.object(self.command_manager, '_handle_project_commands', return_value=None):
                with patch.object(self.command_manager, '_handle_shell_commands', return_value=None):
                    with patch.object(self.command_manager, '_handle_development_commands', return_value=None):
                        with patch.object(self.command_manager, '_handle_service_generator_commands', return_value=None):
                            with patch.object(self.command_manager, '_handle_info_commands', return_value=None):
                                result = self.command_manager.handle_command('check', args)
                                assert result is None
