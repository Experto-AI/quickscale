# Authentication Template Documentation

This document provides comprehensive information about the authentication-related templates in QuickScale projects. It covers naming conventions, template organization, styling guidelines, and customization examples.

## Template Directory Structure

Authentication templates are organized as follows:

```
templates/
├── account/               # Django-allauth specific templates
│   ├── email/             # Email template files
│   │   ├── base_message.txt         # Base email template
│   │   ├── email_confirmation_message.txt
│   │   ├── email_confirmation_subject.txt
│   │   ├── password_reset_key_message.txt
│   │   └── password_reset_key_subject.txt
│   ├── base.html          # Base template for account pages
│   ├── login.html         # Login page
│   ├── signup.html        # Signup page
│   ├── password_reset.html # Password reset request
│   ├── password_reset_done.html # After password reset request
│   ├── password_reset_from_key.html # Set new password
│   ├── verification_sent.html  # Email verification sent
│   └── verified_email_required.html # Requires email verification
├── users/                 # Custom user management templates
│   ├── profile.html       # User profile page
│   ├── profile_form.html  # HTMX-updatable profile form
│   ├── login.html         # Custom login page
│   ├── login_form.html    # HTMX-updatable login form
│   └── signup.html        # Custom signup page
└── components/            # Reusable components
    ├── messages.html      # Flash messages
    └── form_field.html    # Reusable form field rendering
```

## Template Naming Conventions

Authentication templates follow these naming conventions:

1. **Base Templates**: Use `base.html` for the foundation template that other templates extend.

2. **Action Templates**: Name templates after the primary action they enable:
   - `login.html` - User login
   - `signup.html` - User registration
   - `password_reset.html` - Initiating password reset
   - `profile.html` - User profile view/edit

3. **HTMX Partial Templates**: For templates that are designed to be loaded via HTMX:
   - Use `_form.html` suffix for forms that can be updated dynamically
   - Example: `login_form.html` for the HTMX-updatable login form

4. **Email Templates**: Located in `account/email/` with consistent naming:
   - `email_confirmation_message.txt` - Email verification message
   - `email_confirmation_subject.txt` - Email verification subject
   - `password_reset_key_message.txt` - Password reset message
   - `password_reset_key_subject.txt` - Password reset subject

5. **State Templates**: Templates that represent state in a process use descriptive suffixes:
   - `_done.html` - Completion state
   - `_sent.html` - Notification sent state
   - `_required.html` - Requirement state

## Styling Guidelines

Authentication templates use Bulma CSS framework and follow these styling guidelines:

1. **Forms**:
   - Wrap form fields in `.field` containers
   - Use `.label` for form labels
   - Use `.control` for input containers
   - Add `.input` class to form inputs
   - Use `.help` for helper text and `.help.is-danger` for error messages

2. **Buttons**:
   - Primary actions use `.button.is-primary`
   - Secondary actions use `.button.is-light`
   - Destructive actions use `.button.is-danger`

3. **Notifications**:
   - Success messages use `.notification.is-success`
   - Error messages use `.notification.is-danger`
   - Info messages use `.notification.is-info`
   - Warning messages use `.notification.is-warning`

4. **Layout**:
   - Center authentication forms with `.columns.is-centered`
   - Use `.box` container for forms
   - Maintain consistent spacing with Bulma spacing helpers

5. **Icons**:
   - Use Font Awesome icons with the `.icon` class
   - Add `.is-small`, `.is-medium`, or `.is-large` to control size

## HTMX Integration

Authentication templates leverage HTMX for dynamic interactions:

1. **Form Submission**: Forms use the following attributes:
   - `hx-post` - Target URL for form submission
   - `hx-target` - Element to update after submission
   - `hx-swap` - How to swap the content (usually `outerHTML`)

2. **Redirects**: After successful actions, the server sets:
   - `HX-Redirect` header to redirect the user

3. **Target Elements**: Forms and content that will be dynamically updated should have meaningful IDs:
   - `#form-container` - For form containers
   - `#profile-form-container` - For profile form

## Customization Examples

### Adding a New Field to the Signup Form

1. Update the `CustomSignupForm` in `users/forms.py`:

```python
# Add a new field
phone_number = forms.CharField(
    max_length=20,
    label=_('Phone Number'),
    required=False,
    widget=forms.TextInput(attrs={
        'placeholder': _('Phone Number'),
        'class': 'input',
    }),
)

# Update the save method
def save(self, request):
    user = super().save(request)
    user.phone_number = self.cleaned_data.get('phone_number', '')
    user.save()
    return user
```

2. Add the field to `account/signup.html`:

```html
<div class="field">
    <label class="label">{{ form.phone_number.label }}</label>
    <div class="control">
        {{ form.phone_number }}
    </div>
    {% if form.phone_number.errors %}
        <p class="help is-danger">{{ form.phone_number.errors.0 }}</p>
    {% endif %}
</div>
```

### Customizing the Login Page

To add a "Remember Me" checkbox to the login form:

```html
<div class="field">
    <div class="control">
        <label class="checkbox">
            <input type="checkbox" name="remember" class="checkbox">
            Remember me
        </label>
    </div>
</div>
```

### Customizing Email Templates

To customize the email verification template, edit `account/email/email_confirmation_message.txt`:

```
{% load i18n %}
{% autoescape off %}
{% blocktrans with site_name=current_site.name %}
Hello from {{ site_name }}!

Please confirm your email address by clicking on the link below:

{{ activate_url }}

This link will expire in 24 hours.

Thank you,
The {{ site_name }} Team
{% endblocktrans %}
{% endautoescape %}
```

## Password Strength Validation

Password strength validation is implemented in two ways:

1. **Client-side**: Using the `password-validation.js` script that adds:
   - Real-time strength meter
   - Visual feedback on password complexity
   - Suggestions for improving password strength

2. **Server-side**: Using Django's password validators in `settings.py`:
   - Django's built-in validators
   - Custom validators in `users/validators.py`
   - `PasswordStrengthValidator` checks for complexity
   - `BreachedPasswordValidator` checks against common passwords

## Email Verification Flow

The email verification workflow follows these steps:

1. User submits signup form
2. System creates account with `is_active=True` but requires verification
3. Verification email is sent using `email_confirmation_message.txt` template
4. User is redirected to `verification_sent.html`
5. User clicks verification link in email
6. System verifies the email and activates full account access
7. User is redirected to login page with success message 