"""Unit tests for the DestroyProjectCommand class."""
import os
import shutil
import unittest
import subprocess
from unittest.mock import patch, MagicMock, call
from pathlib import Path

from quickscale.commands.project_commands import DestroyProjectCommand
from quickscale.commands.project_manager import ProjectManager


class TestDestroyProjectCommand(unittest.TestCase):
    """Test cases for the DestroyProjectCommand class."""
    
    def setUp(self):
        """Set up the test environment."""
        self.command = DestroyProjectCommand()
    
    def test_confirm_destruction_confirmed(self):
        """Test that _confirm_destruction returns True when user confirms."""
        with patch('builtins.input', return_value='y'):
            result = self.command._confirm_destruction('test-project')
            self.assertTrue(result)
    
    def test_confirm_destruction_denied(self):
        """Test that _confirm_destruction returns False when user denies."""
        for input_value in ['n', 'N', '', 'no', 'anything_else']:
            with patch('builtins.input', return_value=input_value):
                result = self.command._confirm_destruction('test-project')
                self.assertFalse(result)
    
    @patch('os.chdir')
    @patch('shutil.rmtree')
    @patch('quickscale.commands.project_manager.ProjectManager.stop_containers')
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    def test_execute_with_project_confirmed(self, mock_get_state, mock_stop, mock_rmtree, mock_chdir):
        """Test executing destroy command with a project and user confirms."""
        # Setup mock to simulate a project in current directory
        mock_get_state.return_value = {
            'has_project': True,
            'project_name': 'test-project',
            'project_dir': '/path/to/test-project',
            'containers': None
        }
        
        # Simulate user confirming the destruction
        with patch.object(self.command, '_confirm_destruction', return_value=True):
            result = self.command.execute()
        
        # Verify the correct functions were called
        mock_stop.assert_called_once_with('test-project')
        mock_chdir.assert_called_once_with('..')
        mock_rmtree.assert_called_once_with('/path/to/test-project')
        
        # Verify the result
        self.assertTrue(result['success'])
        self.assertEqual(result['project'], 'test-project')
    
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    def test_execute_with_project_cancelled(self, mock_get_state):
        """Test executing destroy command with a project but user cancels."""
        # Setup mock to simulate a project in current directory
        mock_get_state.return_value = {
            'has_project': True,
            'project_name': 'test-project',
            'project_dir': '/path/to/test-project',
            'containers': None
        }
        
        # Simulate user cancelling the destruction
        with patch.object(self.command, '_confirm_destruction', return_value=False):
            result = self.command.execute()
        
        # Verify the result indicates cancellation
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'cancelled')
    
    @patch('builtins.input', return_value='y')
    @patch('shutil.rmtree')
    @patch('quickscale.commands.project_manager.ProjectManager.stop_containers')
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    def test_execute_with_containers_and_directory(self, mock_get_state, mock_stop, mock_rmtree, mock_input):
        """Test executing destroy command with containers and directory but no project in current directory."""
        # Setup mock to simulate containers and directory
        mock_get_state.return_value = {
            'has_project': False,
            'containers': {
                'project_name': 'test-project',
                'containers': ['web', 'db'],
                'has_directory': True
            }
        }
        
        result = self.command.execute()
        
        # Verify the correct functions were called
        mock_stop.assert_called_once_with('test-project')
        mock_rmtree.assert_called_once_with(Path('test-project'))
        
        # Verify the result
        self.assertTrue(result['success'])
        self.assertEqual(result['project'], 'test-project')
    
    @patch('builtins.input', return_value='n')
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    def test_execute_with_containers_and_directory_cancelled(self, mock_get_state, mock_input):
        """Test executing destroy command with containers and directory but user cancels."""
        # Setup mock to simulate containers and directory
        mock_get_state.return_value = {
            'has_project': False,
            'containers': {
                'project_name': 'test-project',
                'containers': ['web', 'db'],
                'has_directory': True
            }
        }
        
        result = self.command.execute()
        
        # Verify the result indicates cancellation
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'cancelled')
    
    @patch('builtins.input', return_value='y')
    @patch('quickscale.commands.project_manager.ProjectManager.stop_containers')
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    def test_execute_with_containers_only(self, mock_get_state, mock_stop, mock_input):
        """Test executing destroy command with containers but no directory."""
        # Setup mock to simulate containers only
        mock_get_state.return_value = {
            'has_project': False,
            'containers': {
                'project_name': 'test-project',
                'containers': ['web', 'db'],
                'has_directory': False
            }
        }
        
        result = self.command.execute()
        
        # Verify the correct functions were called
        mock_stop.assert_called_once_with('test-project')
        
        # Verify the result
        self.assertTrue(result['success'])
        self.assertTrue(result['containers_only'])
    
    @patch('builtins.input', return_value='n')
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    def test_execute_with_containers_only_cancelled(self, mock_get_state, mock_input):
        """Test executing destroy command with containers only but user cancels."""
        # Setup mock to simulate containers only
        mock_get_state.return_value = {
            'has_project': False,
            'containers': {
                'project_name': 'test-project',
                'containers': ['web', 'db'],
                'has_directory': False
            }
        }
        
        result = self.command.execute()
        
        # Verify the result indicates cancellation
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'cancelled')
    
    @patch('builtins.print')
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    @patch('quickscale.commands.project_manager.ProjectManager.PROJECT_NOT_FOUND_MESSAGE', 'No project found')
    def test_execute_with_no_project_or_containers(self, mock_get_state, mock_print):
        """Test executing destroy command with no project or containers."""
        # Setup mock to simulate no project or containers
        mock_get_state.return_value = {
            'has_project': False,
            'containers': None
        }
        
        result = self.command.execute()
        
        # Verify the error message was printed
        mock_print.assert_called_with('No project found')
        
        # Verify the result
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'no_project')
    
    @patch('builtins.print')
    @patch('quickscale.utils.logging_manager.LoggingManager.get_logger')
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    def test_execute_with_subprocess_error(self, mock_get_state, mock_get_logger, mock_print):
        """Test executing destroy command with a subprocess error."""
        # Setup mock to throw a subprocess error
        mock_get_state.return_value = {
            'has_project': True,
            'project_name': 'test-project',
            'project_dir': '/path/to/test-project',
            'containers': None
        }
        
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        # Simulate user confirming but subprocess failing
        with patch.object(self.command, '_confirm_destruction', return_value=True):
            with patch('quickscale.commands.project_manager.ProjectManager.stop_containers', 
                      side_effect=subprocess.SubprocessError('Command failed')):
                result = self.command.execute()
        
        # Verify the error message was printed
        mock_print.assert_any_call('[ERROR] Container operation error: Command failed')
        
        # Verify the result
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'subprocess_error')
        self.assertEqual(result['error'], 'Command failed')
    
    @patch('builtins.print')
    @patch('quickscale.utils.logging_manager.LoggingManager.get_logger')
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state')
    def test_execute_with_general_exception(self, mock_get_state, mock_get_logger, mock_print):
        """Test executing destroy command with a general exception."""
        # Setup mock to throw a general exception
        mock_get_state.side_effect = Exception('Something went wrong')
        
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        result = self.command.execute()
        
        # Verify the error message was printed
        mock_print.assert_any_call('[ERROR] Project destruction error: Something went wrong')
        
        # Verify the result
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'error')
        self.assertEqual(result['error'], 'Something went wrong') 