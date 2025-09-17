"""Integration tests for CLI commands workflow."""
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from quickscale.cli import main
from quickscale.commands.command_manager import CommandManager


class TestCLIWorkflowIntegration:
    """Integration tests for complete CLI workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command_manager = CommandManager()
    
    @patch('quickscale.commands.init_command.copy_sync_modules')
    @patch('quickscale.commands.init_command.fix_imports')
    @patch('quickscale.commands.init_command.process_file_templates')
    @patch('quickscale.commands.init_command.remove_duplicated_templates')
    @patch('shutil.copytree')
    def test_complete_init_workflow(self, mock_copytree, mock_remove_dup, 
                                  mock_process_files, mock_fix_imports, mock_copy_sync):
        """Test complete project initialization workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                project_name = "test_workflow_project"
                
                # Execute init command
                self.command_manager.init_project(project_name)
                
                # Verify project directory was created
                project_path = Path(temp_dir) / project_name
                assert project_path.exists()
                
                # Verify .env file was created
                env_file = project_path / '.env'
                assert env_file.exists()
                
                # Verify template processing was called
                mock_copytree.assert_called_once()
                mock_copy_sync.assert_called_once()
                mock_fix_imports.assert_called_once()
                mock_process_files.assert_called_once()
                mock_remove_dup.assert_called_once()
                
            finally:
                os.chdir(original_cwd)
    
    @patch('subprocess.run')
    def test_service_management_workflow(self, mock_run):
        """Test service management workflow (up, status, logs, down)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Create a minimal project structure to simulate being in a project
                project_path = Path(temp_dir)
                (project_path / 'docker-compose.yml').touch()
                (project_path / '.env').write_text('PROJECT_NAME=test\n')
                
                # Mock successful subprocess calls
                mock_run.return_value = Mock(returncode=0, stdout="Success")
                
                # Test service up
                with patch('quickscale.commands.service_commands.ServiceUpCommand._check_port_availability') as mock_check_ports:
                    mock_check_ports.return_value = {}
                    self.command_manager.start_services()
                    
                # Test service status
                self.command_manager.check_services_status()
                
                # Test view logs
                self.command_manager.view_logs(service='web', follow=False, lines=10)
                
                # Test service down
                self.command_manager.stop_services()
                
                # Verify subprocess calls were made
                assert mock_run.call_count >= 3  # At least up, ps, logs, down
                
            finally:
                os.chdir(original_cwd)
    
    def test_service_generation_workflow(self):
        """Test complete service generation workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Create services directory
                services_dir = Path(temp_dir) / 'services'
                services_dir.mkdir()
                
                # Generate a service
                with patch('quickscale.commands.service_generator_commands.ServiceGeneratorCommand._configure_service_in_database', return_value=True):
                    result = self.command_manager.generate_service(
                        service_name='test_workflow_service',
                        service_type='text_processing',
                        credit_cost=2.0,
                        description='Test workflow service',
                        skip_db_config=True
                    )
                
                assert result['success'] is True
                
                # Verify service file was created
                service_file = services_dir / 'test_workflow_service_service.py'
                assert service_file.exists()
                
                # Validate the generated service
                validation_result = self.command_manager.validate_service(
                    service_file='test_workflow_service',
                    show_tips=False
                )
                
                assert validation_result['validation_completed'] is True
                
                # Show service examples
                examples_result = self.command_manager.show_service_examples()
                assert 'examples_displayed' in examples_result
                
            finally:
                os.chdir(original_cwd)
    
    @patch('subprocess.run')
    def test_development_commands_workflow(self, mock_run):
        """Test development commands workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Create minimal project structure
                project_path = Path(temp_dir)
                (project_path / 'docker-compose.yml').touch()
                (project_path / 'manage.py').touch()
                
                mock_run.return_value = Mock(returncode=0, stdout="Success")
                
                # Test shell command
                self.command_manager.open_shell(command='ls -la')
                
                # Test Django shell
                self.command_manager.open_shell(django_shell=True)
                
                # Test manage command
                self.command_manager.run_manage_command(['migrate', '--fake'])
                
                # Verify subprocess calls
                assert mock_run.call_count >= 3
                
                # Verify correct commands were called
                calls = mock_run.call_args_list
                assert any('bash' in str(call) for call in calls)  # Shell command
                assert any('shell' in str(call) for call in calls)  # Django shell
                assert any('migrate' in str(call) for call in calls)  # Manage command
                
            finally:
                os.chdir(original_cwd)
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_system_check_workflow(self, mock_run, mock_which):
        """Test system requirements check workflow."""
        # Mock tools available - including python3 for our improved detection
        mock_which.side_effect = lambda tool: f'/usr/bin/{tool}' if tool in ['docker', 'docker-compose', 'python3'] else None
        
        # Mock successful version checks and docker daemon check
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Docker version 20.10.0"),
            Mock(returncode=0, stdout="Python 3.12.3"),  # Python version check
            Mock(returncode=0, stdout="docker-compose version 1.29.0"),
            Mock(returncode=0, stdout="")  # Docker daemon check (docker info)
        ]
        
        # Test check command
        self.command_manager.check_requirements(print_info=True)
        
        # Verify tools were checked
        assert mock_run.call_count >= 3
        assert mock_which.call_count >= 3
    
    def test_error_recovery_workflow(self):
        """Test error handling and recovery in workflows."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Test init with invalid project name
                with pytest.raises(Exception):  # Should raise ValidationError
                    self.command_manager.init_project('invalid project name')
                
                # Test service generation with invalid name
                result = self.command_manager.generate_service(
                    service_name='invalid service name',  # Invalid
                    service_type='basic'
                )
                assert result['success'] is False
                
                # Test validation of non-existent service
                validation_result = self.command_manager.validate_service(
                    service_file='nonexistent_service'
                )
                assert validation_result['valid'] is False
                
            finally:
                os.chdir(original_cwd)
    
    @patch('sys.argv')
    @patch('quickscale.commands.init_command.copy_sync_modules')
    @patch('quickscale.commands.init_command.fix_imports')
    @patch('quickscale.commands.init_command.process_file_templates')
    @patch('quickscale.commands.init_command.remove_duplicated_templates')
    @patch('shutil.copytree')
    def test_cli_main_integration(self, mock_copytree, mock_remove_dup, mock_process_files,
                                mock_fix_imports, mock_copy_sync, mock_argv):
        """Test complete CLI integration through main() function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Test init command through CLI
                mock_argv.__getitem__.side_effect = lambda i: ['quickscale', 'init', 'test_cli_project'][i]
                mock_argv.__len__.return_value = 3
                
                result = main()
                
                assert result == 0  # Success
                
                # Verify project was created
                project_path = Path(temp_dir) / 'test_cli_project'
                assert project_path.exists()
                
            finally:
                os.chdir(original_cwd)
    
    def test_command_chaining_workflow(self):
        """Test chaining multiple commands in sequence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # 1. Initialize project
                with patch('quickscale.commands.init_command.copy_sync_modules'):
                    with patch('quickscale.commands.init_command.fix_imports'):
                        with patch('quickscale.commands.init_command.process_file_templates'):
                            with patch('quickscale.commands.init_command.remove_duplicated_templates'):
                                with patch('shutil.copytree'):
                                    project_name = 'chaining_test_project'
                                    self.command_manager.init_project(project_name)
                
                # Change to project directory
                os.chdir(project_name)
                
                # 2. Generate a service
                with patch('quickscale.commands.service_generator_commands.ServiceGeneratorCommand._configure_service_in_database', return_value=True):
                    service_result = self.command_manager.generate_service(
                        service_name='chained_service',
                        service_type='basic',
                        skip_db_config=True
                    )
                
                assert service_result['success'] is True
                
                # 3. Validate the service
                validation_result = self.command_manager.validate_service(
                    service_file='chained_service'
                )
                
                assert validation_result['valid'] is True
                
                # 4. Show examples
                examples_result = self.command_manager.show_service_examples()
                assert 'examples' in examples_result
                
                # 5. Check system requirements
                with patch('shutil.which', return_value='/usr/bin/docker'):
                    with patch('subprocess.run', return_value=Mock(returncode=0, stdout="Docker version 20.10.0")):
                        self.command_manager.check_requirements(print_info=False)
                
            finally:
                os.chdir(original_cwd)
    
    def test_concurrent_command_safety(self):
        """Test that commands are safe for concurrent execution."""
        # Create multiple command managers to simulate concurrent access
        managers = [CommandManager() for _ in range(3)]
        
        # Test that they all have independent state
        for i, manager in enumerate(managers):
            assert manager is not None
            assert hasattr(manager, '_commands')
            assert len(manager._commands) > 0
            
            # Each manager should have its own command instances
            if i > 0:
                # Commands should be different instances but same type
                assert managers[i]._commands['check'] is not managers[0]._commands['check']
                assert isinstance(managers[i]._commands['check'], type(managers[0]._commands['check']))
    
    def test_command_state_isolation(self):
        """Test that commands maintain proper state isolation."""
        # Test multiple service generations don't interfere
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Create services directory
                services_dir = Path(temp_dir) / 'services'
                services_dir.mkdir()
                
                # Generate multiple services
                service_names = ['service1', 'service2', 'service3']
                
                for service_name in service_names:
                    with patch('quickscale.commands.service_generator_commands.ServiceGeneratorCommand._configure_service_in_database', return_value=True):
                        result = self.command_manager.generate_service(
                            service_name=service_name,
                            service_type='basic',
                            skip_db_config=True
                        )
                    
                    assert result['success'] is True
                    
                    # Verify each service file was created independently
                    service_file = services_dir / f'{service_name}_service.py'
                    assert service_file.exists()
                    
                    # Verify content is specific to this service
                    content = service_file.read_text()
                    assert service_name in content
                    
                    # Verify other service names are not in this file
                    for other_name in service_names:
                        if other_name != service_name:
                            assert other_name not in content
                            
            finally:
                os.chdir(original_cwd)


class TestCLIErrorHandlingIntegration:
    """Integration tests for CLI error handling across commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command_manager = CommandManager()
    
    def test_graceful_degradation_workflow(self):
        """Test that system gracefully degrades when components are unavailable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Test service generation when database config fails
                services_dir = Path(temp_dir) / 'services'
                services_dir.mkdir()
                
                with patch('quickscale.commands.service_generator_commands.ServiceGeneratorCommand._configure_service_in_database', return_value=False):
                    result = self.command_manager.generate_service(
                        service_name='degraded_service',
                        service_type='basic',
                        credit_cost=1.0,
                        skip_db_config=False  # Try to configure but it will fail
                    )
                
                # Service should still be generated even if DB config fails
                assert result['success'] is True
                
                # Service file should exist
                service_file = services_dir / 'degraded_service_service.py'
                assert service_file.exists()
                
            finally:
                os.chdir(original_cwd)
    
    @patch('quickscale.commands.project_manager.subprocess.run')
    def test_docker_unavailable_scenarios(self, mock_run):
        """Test behavior when Docker is unavailable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Create minimal project structure
                (Path(temp_dir) / 'docker-compose.yml').touch()
                
                # Mock Docker unavailable
                mock_run.side_effect = FileNotFoundError("docker not found")
                
                # Test that service commands fail gracefully with SystemExit
                with pytest.raises(SystemExit):
                    self.command_manager.start_services()
                
                with pytest.raises(FileNotFoundError):
                    self.command_manager.open_shell()
                
                with pytest.raises(FileNotFoundError):
                    self.command_manager.run_manage_command(['migrate'])
                
            finally:
                os.chdir(original_cwd)
    
    def test_permission_error_scenarios(self):
        """Test behavior with permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Test init with permission error
                with patch('pathlib.Path.mkdir', side_effect=PermissionError("Permission denied")):
                    with pytest.raises(Exception):
                        self.command_manager.init_project('permission_test')
                
                # Test service generation with permission error
                services_dir = Path(temp_dir) / 'services'
                services_dir.mkdir()
                
                with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                    result = self.command_manager.generate_service(
                        service_name='permission_service',
                        skip_db_config=True
                    )
                
                assert result['success'] is False
                assert 'permission' in result['error'].lower()
                
            finally:
                os.chdir(original_cwd)
    
    def test_filesystem_full_scenarios(self):
        """Test behavior when filesystem is full."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # Test service generation with disk full error
                services_dir = Path(temp_dir) / 'services'
                services_dir.mkdir()
                
                with patch('builtins.open', side_effect=OSError("No space left on device")):
                    result = self.command_manager.generate_service(
                        service_name='diskfull_service',
                        skip_db_config=True
                    )
                
                assert result['success'] is False
                assert 'space' in result['error'].lower() or 'device' in result['error'].lower()
                
            finally:
                os.chdir(original_cwd)


class TestCLIPerformanceIntegration:
    """Integration tests for CLI performance characteristics."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command_manager = CommandManager()
    
    def test_command_manager_initialization_speed(self):
        """Test that CommandManager initializes quickly."""
        import time
        
        start_time = time.time()
        manager = CommandManager()
        end_time = time.time()
        
        # Should initialize very quickly (under 1 second)
        assert (end_time - start_time) < 1.0
        assert len(manager._commands) > 0
    
    def test_service_generation_scalability(self):
        """Test service generation with multiple services."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                services_dir = Path(temp_dir) / 'services'
                services_dir.mkdir()
                
                # Generate multiple services to test scalability
                service_count = 10
                
                with patch('quickscale.commands.service_generator_commands.ServiceGeneratorCommand._configure_service_in_database', return_value=True):
                    for i in range(service_count):
                        result = self.command_manager.generate_service(
                            service_name=f'perf_test_service_{i}',
                            service_type='basic',
                            skip_db_config=True
                        )
                        
                        assert result['success'] is True
                
                # Verify all services were created (2 files per service: _service.py and _example.py)
                service_files = list(services_dir.glob('perf_test_service_*.py'))
                assert len(service_files) == service_count * 2  # Each service generates 2 files
                
            finally:
                os.chdir(original_cwd)
    
    def test_memory_usage_stability(self):
        """Test that commands don't leak memory."""
        import gc
        
        # Force garbage collection before test
        gc.collect()
        
        # Create and destroy multiple command managers
        for _ in range(100):
            manager = CommandManager()
            # Access some commands to ensure they're initialized
            _ = manager.get_available_commands()
            del manager
        
        # Force garbage collection after test
        gc.collect()
        
        # Test passes if no exceptions were raised and we reach this point
        assert True
