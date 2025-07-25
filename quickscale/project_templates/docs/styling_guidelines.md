# Authentication Components Styling Guidelines

This document provides detailed styling guidelines for authentication components in QuickScale projects. These guidelines ensure consistency across all authentication-related UI elements and maintain the clean, modern aesthetic of the application.

## Form Elements

### Text Inputs

All text inputs should use Bulma's input classes with consistent styling:

```html
<div class="field">
  <label class="label">Email</label>
  <div class="control">
    <input class="input" type="email" name="email" placeholder="your.email@example.com">
  </div>
</div>
```

For inputs with icons:

```html
<div class="field">
  <label class="label">Email</label>
  <div class="control has-icons-left">
    <input class="input" type="email" name="email" placeholder="your.email@example.com">
    <span class="icon is-small is-left">
      <i class="fas fa-envelope"></i>
    </span>
  </div>
</div>
```

### Select Inputs

```html
<div class="field">
  <label class="label">Country</label>
  <div class="control">
    <div class="select">
      <select name="country">
        <option value="">Select your country</option>
        <option value="us">United States</option>
        <option value="ca">Canada</option>
        <!-- More options... -->
      </select>
    </div>
  </div>
</div>
```

### Checkboxes & Radio Buttons

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

```html
<div class="field">
  <div class="control">
    <label class="radio">
      <input type="radio" name="notification_preference" value="email">
      Email
    </label>
    <label class="radio">
      <input type="radio" name="notification_preference" value="sms">
      SMS
    </label>
  </div>
</div>
```

### File Inputs

```html
<div class="field">
  <label class="label">Profile Picture</label>
  <div class="file has-name">
    <label class="file-label">
      <input type="file" name="profile_picture" class="file-input">
      <span class="file-cta">
        <span class="file-icon">
          <i class="fas fa-upload"></i>
        </span>
        <span class="file-label">
          Choose a file…
        </span>
      </span>
      <span class="file-name">
        No file chosen
      </span>
    </label>
  </div>
</div>
```

### Text Areas

```html
<div class="field">
  <label class="label">Bio</label>
  <div class="control">
    <textarea class="textarea" name="bio" rows="4" placeholder="Tell us about yourself"></textarea>
  </div>
</div>
```

### Form Layout

Forms should be laid out with consistent spacing and organization:

- Use `.field` containers for form fields
- Use `.control` for input containers
- Use `.columns` for multi-column layouts
- Use appropriate spacing classes (e.g., `mt-4`, `mb-3`)
- Group related fields together

## Buttons

### Primary Buttons

Used for main form submission actions:

```html
<button type="submit" class="button is-primary is-fullwidth">
  Log In
</button>
```

### Secondary Buttons

Used for alternative actions:

```html
<button type="button" class="button is-light">
  Cancel
</button>
```

### Destructive Buttons

Used for actions that delete or remove data:

```html
<button type="button" class="button is-danger">
  Delete Account
</button>
```

### Button with Icons

```html
<button type="button" class="button is-primary">
  <span class="icon">
    <i class="fas fa-save"></i>
  </span>
  <span>Save</span>
</button>
```

## Notifications & Messages

### Success Messages

```html
<div class="notification is-success">
  <button class="delete"></button>
  Your profile has been updated successfully!
</div>
```

### Error Messages

```html
<div class="notification is-danger">
  <button class="delete"></button>
  There was a problem with your submission. Please check the errors below.
</div>
```

### Warning Messages

```html
<div class="notification is-warning">
  <button class="delete"></button>
  Your password will expire in 7 days. Please update it soon.
</div>
```

### Info Messages

```html
<div class="notification is-info">
  <button class="delete"></button>
  Check your email for a verification link.
</div>
```

## Form Error Messages

Error messages should be displayed below the relevant form field:

```html
<div class="field">
  <label class="label">Email</label>
  <div class="control">
    <input class="input is-danger" type="email" name="email">
  </div>
  <p class="help is-danger">Please enter a valid email address.</p>
</div>
```

## Color Palette

Use Bulma's color system consistently:

- Primary: Blue (`is-primary`) - Main actions, links
- Success: Green (`is-success`) - Success messages, completed actions
- Danger: Red (`is-danger`) - Error messages, destructive actions
- Warning: Yellow (`is-warning`) - Warning messages, caution actions
- Info: Light blue (`is-info`) - Informational messages
- Light: Light gray (`is-light`) - Secondary actions, background

## Typography

Use Bulma's typography classes consistently:

- `.title` and `.subtitle` for headings
- `.is-1` through `.is-7` for different heading sizes
- `.has-text-centered` for centered text
- `.has-text-weight-bold` for bold text
- `.is-size-*` for specific text sizes

## Responsive Design

Ensure all authentication forms are responsive:

- Use `.columns.is-multiline` for multi-column layouts
- Use `.column.is-*-mobile`, `.column.is-*-tablet`, `.column.is-*-desktop` for responsive columns
- Test forms on mobile, tablet, and desktop viewports
- Ensure tap targets are at least 44px in size for mobile users

## Accessibility

Ensure authentication components are accessible:

- Use proper `label` elements for form fields
- Use `aria-*` attributes where appropriate
- Ensure color contrast meets WCAG AA standards
- Provide helpful error messages for form validation
- Use semantic HTML elements (e.g., `<button>` instead of `<div>` for buttons)

## Example: Complete Login Form

```html
<div class="box">
  <form method="post" action="{% url 'account_login' %}" hx-post="{% url 'account_login' %}" hx-target="#form-container" hx-swap="outerHTML">
    {% csrf_token %}
    
    {% if form.non_field_errors %}
    <div class="notification is-danger">
      <button class="delete"></button>
      {% for error in form.non_field_errors %}
        {{ error }}
      {% endfor %}
    </div>
    {% endif %}
    
    <div class="field">
      <label class="label">Email</label>
      <div class="control has-icons-left">
        <input class="input" type="email" name="email" placeholder="your.email@example.com" required>
        <span class="icon is-small is-left">
          <i class="fas fa-envelope"></i>
        </span>
      </div>
      {% if form.email.errors %}
      <p class="help is-danger">{{ form.email.errors.0 }}</p>
      {% endif %}
    </div>

    <div class="field">
      <label class="label">Password</label>
      <div class="control has-icons-left">
        <input class="input" type="password" name="password" placeholder="********" required>
        <span class="icon is-small is-left">
          <i class="fas fa-lock"></i>
        </span>
      </div>
      {% if form.password.errors %}
      <p class="help is-danger">{{ form.password.errors.0 }}</p>
      {% endif %}
    </div>

    <div class="field">
      <div class="control">
        <label class="checkbox">
          <input type="checkbox" name="remember">
          Remember me
        </label>
      </div>
    </div>

    <div class="field">
      <div class="control">
        <button type="submit" class="button is-primary is-fullwidth">
          Log In
        </button>
      </div>
    </div>
  </form>
  
  <div class="has-text-centered mt-4">
    <p>Don't have an account? <a href="{% url 'account_signup' %}">Sign up</a></p>
    <p><a href="{% url 'account_reset_password' %}">Forgot password?</a></p>
  </div>
</div>
```

## Implementation Notes

1. Always use the Bulma CSS framework for styling
2. Use Font Awesome for icons (via the CDN included in the base template)
3. Use consistent spacing with Bulma's spacing helpers
4. Follow the example templates in the QuickScale template directory
5. Maintain consistent naming conventions for CSS classes and IDs 