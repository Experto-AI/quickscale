# Development Workflow

## QuickScale Development Process

QuickScale uses a streamlined development workflow optimized for AI-assisted development and template-based project generation.

## Core Development Commands

### Project Lifecycle
```bash
# Initialize new project
quickscale init my-project

# Start development environment
quickscale up

# Stop environment
quickscale down

# Build and update templates
quickscale build

# Sync improvements back to templates
quickscale sync-back --preview
quickscale sync-back --apply
```

### Development Environment
```bash
# Check status
quickscale status

# View logs
quickscale logs

# Run tests
quickscale test

# Database management
quickscale db migrate
quickscale db shell
```

## AI-Assisted Development Workflow

### 1. Planning Phase
- Understand user requirements and project context
- Analyze existing architecture and patterns
- Plan implementation steps with SOLID principles
- Define clear task boundaries and scope

### 2. Implementation Phase
- Generate development project with `quickscale init`
- Modify templates with AI visual feedback system
- Use hot reload for immediate visual validation
- Follow established code patterns and conventions

### 3. Quality Control Phase
- Verify SOLID principles compliance
- Run automated tests and validation
- Check documentation completeness
- Validate interface preservation

### 4. Template Integration
- Preview changes with `quickscale sync-back --preview`
- Apply validated changes to QuickScale templates
- Update tests and documentation as needed
- Verify future project generation works correctly

## Installation Modes

### Development Mode (Recommended for Contributors)
```bash
git clone https://github.com/Experto-AI/quickscale.git
cd quickscale
pip install -e .
```

**Benefits:**
- Full sync-back functionality
- Template modification capabilities
- Direct code changes reflected immediately
- Complete development tooling

### Production Mode (End Users)
```bash
pip install quickscale
```

**Limitations:**
- Sync-back disabled (templates read-only)
- No template modification capabilities
- Guidance provided for switching to development mode

## Template Development Patterns

### Template File Organization
```
quickscale/project_templates/
├── project_name/
│   ├── settings/
│   ├── templates/
│   ├── static/
│   └── apps/
├── users/
├── credits/
└── docs/
```

### Template Variables
- `{{project_name}}` - Project name
- `{{app_name}}` - App name  
- `{{model_name}}` - Model name
- Environment-specific configurations in `.env` templates

### Template Testing Strategy
1. **Generation Testing** - Verify templates generate valid code
2. **Syntax Validation** - Check Python and HTML syntax
3. **Integration Testing** - Test complete workflows
4. **Sample Projects** - Validate generated project functionality

## Git Workflow

### Branch Strategy
- `main` - Stable releases
- `develop` - Development integration
- `feature/*` - Feature development
- `fix/*` - Bug fixes

### Commit Conventions
```
type(scope): description

feat(templates): add new billing template
fix(cli): resolve database connection issue
docs(readme): update installation instructions
test(credits): add credit consumption tests
```

## Code Quality Standards

### Python Code Standards
- **Type Hints**: Use specific type annotations
- **Docstrings**: Document functionality (not parameters/returns)
- **Error Handling**: Use exceptions, not return codes
- **Logging**: Structured logging instead of print statements
- **Imports**: Group and organize logically

### Template Standards
- **HTML5 Compliance**: Modern, semantic markup
- **HTMX Integration**: Progressive enhancement patterns
- **Alpine.js**: Minimal, declarative JavaScript
- **CSS Organization**: Component-based stylesheets
- **Accessibility**: WCAG 2.1 AA compliance

### Documentation Standards
- **Concise**: Essential information only
- **Actionable**: Clear next steps
- **Context-Aware**: For both humans and AI assistants
- **Examples**: Practical code samples
- **Architecture-Focused**: System understanding over implementation details

## Testing Workflow

### Test Categories
1. **Unit Tests** - Individual component testing
2. **Template Generation Tests** - Verify correct code generation  
3. **Integration Tests** - End-to-end workflow validation
4. **Sample Project Tests** - Basic functionality verification

### Test Execution
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/template_generation/

# Run with coverage
pytest --cov=quickscale

# Generate coverage report
pytest --cov=quickscale --cov-report=html
```

### Test Development Guidelines
- **Test-Driven Development**: Write tests before implementation
- **Behavior-Focused**: Test outcomes, not implementation
- **Mock External Dependencies**: Isolate units under test
- **Descriptive Names**: Clear test purpose and expectations

## AI Assistant Integration

### Context Management
- Use semantic search for codebase understanding
- Read large file sections for complete context
- Leverage grep search for specific patterns
- Maintain conversation context across tool calls

### Tool Usage Patterns
- **Parallel Tool Calls**: When operations are independent
- **Sequential Tool Calls**: For dependent operations
- **Context Building**: Gather information before implementation
- **Validation**: Verify changes after implementation

### Best Practices
- **Understand Before Acting**: Analyze existing patterns
- **Preserve Interfaces**: Maintain backward compatibility
- **Follow Conventions**: Match existing code style
- **Incremental Changes**: Small, focused modifications
- **Validate Results**: Test changes thoroughly

## Debugging and Problem Resolution

### Systematic Debugging
1. **Define Problem**: Clear symptoms and success criteria
2. **Gather Data**: Logs, error messages, reproduction steps
3. **Analyze Root Cause**: Systematic investigation
4. **Implement Solution**: Address fundamental cause
5. **Prevent Regression**: Add tests and monitoring

### Common Issues
- **Template Generation Errors**: Check syntax and variable substitution
- **Database Issues**: Verify environment variables and migrations
- **Stripe Integration**: Validate API keys and webhook configuration
- **Docker Problems**: Check port conflicts and volume mounts

### Debugging Tools
- **Django Debug Toolbar**: Development debugging
- **Logging**: Structured application logging
- **pytest**: Test-driven debugging
- **Docker logs**: Container-level debugging

This workflow ensures consistent, high-quality development while supporting both human developers and AI assistants in their collaboration on QuickScale.
