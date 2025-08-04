# Architecture Overview

## System Architecture

QuickScale is a Django SaaS project generator that creates production-ready applications with integrated billing, authentication, and AI service frameworks.

### Core Components

1. **Project Generator** - Template-based Django project creation
2. **Credit System** - Flexible billing with pay-as-you-go and subscription models
3. **Authentication System** - Email-only auth with allauth integration
4. **API Framework** - Secure API key management and middleware
5. **Stripe Integration** - Payment processing and subscription management
6. **CLI Interface** - Command-line tools with standardized messaging

### Technical Stack

- **Backend**: Django 5.0.1+, PostgreSQL, Redis (optional)
- **Frontend**: HTMX + Alpine.js for reactive UIs
- **Payments**: Stripe + dj-stripe for billing
- **Authentication**: django-allauth (email-only)
- **Deployment**: Docker, Uvicorn ASGI server
- **Static Files**: Whitenoise for production serving

## AI-Assisted Visual Development System

QuickScale supports AI-assisted development through a visual feedback system that enables AI assistants to see and modify web interfaces.

### The Vision

Create a development system where AI assistants can:
- **See** the current webpage state (HTML + visual appearance)
- **Analyze** what needs to be changed based on user requests
- **Modify** QuickScale template files directly
- **Observe** immediate results in the running project
- **Iterate** based on visual feedback

### Key Innovation: HTML-First Approach

Instead of modifying CSS directly, the system focuses on HTML structure modifications:

1. **AI analyzes** current HTML structure and visual requirements
2. **System generates** new HTML with appropriate classes
3. **Templates update** automatically with new structure
4. **Browser reflects** changes with hot reload

### Development Workflow Integration

The AI visual system integrates with QuickScale's reverse development workflow:

1. **Generate Project**: Create development instance with `quickscale init`
2. **Visual Development**: AI assistant modifies templates with visual feedback
3. **Live Preview**: See changes immediately in browser
4. **Template Sync**: Sync improvements back to QuickScale templates
5. **Future Projects**: New projects automatically include improvements

### Implementation Architecture

```
AI Assistant
    ↓ (analyzes visual requirements)
HTML Analysis System
    ↓ (generates new HTML structure)
Template Engine
    ↓ (updates template files)
Hot Reload System
    ↓ (reflects changes)
Browser Preview
    ↓ (provides visual feedback)
AI Assistant (iterates)
```

## Reverse Development Workflow

QuickScale uses a reverse development workflow for template improvements:

### The Challenge

Traditional workflow:
1. Modify templates in QuickScale → 2. Test in generated project → 3. Repeat

Better workflow:
1. Generate project → 2. Develop with hot reload → 3. Sync back to templates

### Installation Mode Awareness

Sync-back behavior depends on QuickScale installation:

- **Development Mode** (git clone + editable install): Full sync-back with template modification
- **Production Mode** (pip install): Sync-back disabled with guidance to switch modes

### Sync-Back Process

```bash
# In your generated project
quickscale sync-back --preview  # Preview changes
quickscale sync-back --apply    # Apply to QuickScale templates
```

The system:
1. **Analyzes** differences between generated project and original templates
2. **Identifies** template files that need updates
3. **Previews** changes before applying
4. **Updates** QuickScale templates safely
5. **Validates** template integrity

### Benefits

- **Faster iteration** with hot reload during development
- **Visual feedback** for UI changes
- **Safe template updates** with preview and validation
- **Automatic propagation** to future projects

## Design Patterns

### Template Architecture

- **Base Templates**: Core layout and navigation
- **Feature Templates**: Reusable components (auth, billing, API)
- **Page Templates**: Specific page implementations
- **Fragment Templates**: HTMX partial responses

### Credit System Architecture

- **Credit Types**: Pay-as-you-go (permanent) and subscription (expiring)
- **Consumption Priority**: Subscription credits consumed first
- **Stripe Integration**: Products as source of truth for pricing
- **Transaction Logging**: Complete audit trail for all credit operations

### API Security Pattern

- **API Key Format**: 4-character prefix + 32-character secret
- **Hashing**: Django password hasher for secure storage
- **Middleware**: Custom authentication for API endpoints
- **Permissions**: Role-based access control integration

## Development Principles

### Code Organization

- **Single Responsibility**: Each module handles one concern
- **DRY Principle**: Shared functionality in reusable components
- **Explicit Failure**: Clear error handling and user feedback
- **SOLID Principles**: Maintainable and extensible code structure

### Template Design

- **Composability**: Small, reusable template components
- **Configurability**: Environment-based feature toggles
- **Extensibility**: Easy customization points for generated projects
- **Standards Compliance**: Modern HTML5, accessible markup

### Testing Strategy

- **Template Generation Testing**: Verify QuickScale generates correct code
- **Integration Testing**: Test complete workflows end-to-end
- **Unit Testing**: Individual component validation
- **Sample Project Testing**: Basic functionality verification

This architecture enables rapid SaaS development while maintaining code quality, security, and scalability.
