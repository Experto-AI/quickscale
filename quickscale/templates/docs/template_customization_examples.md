# Template Customization Examples

This document provides examples of common customizations for authentication templates in QuickScale projects.

## Environment Variables in Templates

QuickScale uses environment variables for configuration, which are made available in templates through context processors.

### Project Name Configuration

The project name is configured through the `PROJECT_NAME` environment variable and is available in all templates:

```env
# In .env file
PROJECT_NAME=MyAwesomeProject  # Default: QuickScale
```

```html
<!-- Using project_name in templates -->
<title>{{ project_name }}</title>
<h1>Welcome to {{ project_name }}</h1>
```

### Context Processor

The project settings are made available through the `core.context_processors.project_settings` context processor, which is automatically configured. This processor provides:

- `project_name`: The configured project name from PROJECT_NAME environment variable

### Default Values

If not specified in the environment, these defaults are used:
- PROJECT_NAME: "QuickScale"

### Example Usage

```html
<!-- In base.html -->
<title>{% block title %}{{ project_name }}{% endblock %}</title>

<!-- In navbar.html -->
<a class="navbar-item" href="{% url 'public:index' %}">
    {{ project_name }}
</a>

<!-- In dashboard/index.html -->
{% block title %}Dashboard - {{ project_name }}{% endblock %}
```

## Customizing the Login Form

### Adding Social Login Buttons (If Social Auth is Enabled)

```html
<!-- In login.html -->
<div class="field">
  <div class="control">
    <button type="submit" class="button is-primary is-fullwidth">
      Log In
    </button>
  </div>
</div>

<div class="divider">OR</div>

<div class="field">
  <div class="control">
    <button type="button" class="button is-info is-fullwidth" onclick="window.location='{% url 'social:begin' 'google-oauth2' %}'">
      <span class="icon">
        <i class="fab fa-google"></i>
      </span>
      <span>Continue with Google</span>
    </button>
  </div>
</div>

<div class="field">
  <div class="control">
    <button type="button" class="button is-dark is-fullwidth" onclick="window.location='{% url 'social:begin' 'github' %}'">
      <span class="icon">
        <i class="fab fa-github"></i>
      </span>
      <span>Continue with GitHub</span>
    </button>
  </div>
</div>
```

### Adding Remember Me Checkbox

```html
<!-- In login.html -->
<div class="field">
  <div class="control">
    <label class="checkbox">
      <input type="checkbox" name="remember">
      Remember me
    </label>
  </div>
</div>
```

### Custom Login Form Layout

```html
<!-- In login.html -->
<div class="columns">
  <div class="column">
    <div class="field">
      <label class="label">Email</label>
      <div class="control has-icons-left">
        <input class="input" type="email" name="email" required>
        <span class="icon is-small is-left">
          <i class="fas fa-envelope"></i>
        </span>
      </div>
    </div>
  </div>
  <div class="column">
    <div class="field">
      <label class="label">Password</label>
      <div class="control has-icons-left">
        <input class="input" type="password" name="password" required>
        <span class="icon is-small is-left">
          <i class="fas fa-lock"></i>
        </span>
      </div>
    </div>
  </div>
</div>
```

## Customizing the Signup Form

### Adding Terms and Conditions Checkbox

```html
<!-- In signup.html -->
<div class="field">
  <div class="control">
    <label class="checkbox">
      <input type="checkbox" name="agree_terms" required>
      I agree to the <a href="/terms/">Terms and Conditions</a> and <a href="/privacy/">Privacy Policy</a>
    </label>
  </div>
</div>
```

### Adding Custom Fields

```html
<!-- In signup.html -->
<div class="field">
  <label class="label">Company Name</label>
  <div class="control">
    <input class="input" type="text" name="company_name">
  </div>
</div>

<div class="field">
  <label class="label">Industry</label>
  <div class="control">
    <div class="select is-fullwidth">
      <select name="industry">
        <option value="">Select your industry</option>
        <option value="technology">Technology</option>
        <option value="healthcare">Healthcare</option>
        <option value="finance">Finance</option>
        <option value="education">Education</option>
        <option value="other">Other</option>
      </select>
    </div>
  </div>
</div>
```

## Customizing Email Templates

### Custom Password Reset Email

```
{% load i18n %}{% autoescape off %}
{% blocktrans with site_name=current_site.name %}Hello from {{ site_name }}!{% endblocktrans %}

{% blocktrans %}You're receiving this email because you or someone else has requested a password reset for your user account.{% endblocktrans %}

{% trans "Please go to the following page and choose a new password:" %}
{{ password_reset_url }}

{% trans "Your username, in case you've forgotten:" %} {{ user.get_username }}

{% trans "Thanks for using our site!" %}

{% blocktrans with site_name=current_site.name %}The {{ site_name }} team{% endblocktrans %}
{% endautoescape %}
```

### Custom Email Verification Message

```
{% load i18n %}{% autoescape off %}
{% blocktrans with site_name=current_site.name %}Welcome to {{ site_name }}!{% endblocktrans %}

{% blocktrans %}You're receiving this email because you've just created an account on our platform.{% endblocktrans %}

{% trans "To confirm your email address, please click on the link below:" %}
{{ activate_url }}

{% trans "This link will expire in 24 hours." %}

{% trans "If you did not register an account, you can safely ignore this email." %}

{% blocktrans with site_name=current_site.name %}Thank you,
The {{ site_name }} Team{% endblocktrans %}
{% endautoescape %}
```

## Customizing Profile Page

### Adding Profile Picture Upload

```html
<!-- In profile.html -->
<div class="columns">
  <div class="column is-4">
    <div class="box has-text-centered">
      {% if user.profile_picture %}
        <figure class="image is-128x128 mx-auto">
          <img class="is-rounded" src="{{ user.profile_picture.url }}" alt="{{ user.get_full_name }}">
        </figure>
      {% else %}
        <figure class="image is-128x128 mx-auto">
          <img class="is-rounded" src="https://bulma.io/images/placeholders/128x128.png" alt="{{ user.get_full_name }}">
        </figure>
      {% endif %}
      
      <div class="file is-small mt-3">
        <label class="file-label">
          <input class="file-input" type="file" name="profile_picture" form="profile-form">
          <span class="file-cta">
            <span class="file-icon">
              <i class="fas fa-upload"></i>
            </span>
            <span class="file-label">
              Change picture
            </span>
          </span>
        </label>
      </div>
    </div>
  </div>
  
  <div class="column is-8">
    <!-- Profile form fields here -->
  </div>
</div>
```

### Adding Social Media Links

```html
<!-- In profile.html -->
<div class="box">
  <h3 class="title is-5">Social Media</h3>
  
  <div class="field">
    <label class="label">Twitter</label>
    <div class="control has-icons-left">
      <input class="input" type="text" name="twitter" value="{{ user.twitter }}">
      <span class="icon is-small is-left">
        <i class="fab fa-twitter"></i>
      </span>
    </div>
    <p class="help">Your Twitter username (without @)</p>
  </div>
  
  <div class="field">
    <label class="label">LinkedIn</label>
    <div class="control has-icons-left">
      <input class="input" type="text" name="linkedin" value="{{ user.linkedin }}">
      <span class="icon is-small is-left">
        <i class="fab fa-linkedin"></i>
      </span>
    </div>
    <p class="help">Your LinkedIn profile name</p>
  </div>
  
  <div class="field">
    <label class="label">GitHub</label>
    <div class="control has-icons-left">
      <input class="input" type="text" name="github" value="{{ user.github }}">
      <span class="icon is-small is-left">
        <i class="fab fa-github"></i>
      </span>
    </div>
    <p class="help">Your GitHub username</p>
  </div>
</div>
```

## Customizing Password Reset

### Custom Password Reset Form

```html
<!-- In password_reset.html -->
<div class="box">
  <h3 class="title is-4 has-text-centered">Reset Your Password</h3>
  <p class="subtitle is-6 has-text-centered">Enter your email address and we'll send you a link to reset your password.</p>
  
  <form method="post" action="{% url 'account_reset_password' %}">
    {% csrf_token %}
    
    <div class="field">
      <label class="label">Email</label>
      <div class="control has-icons-left">
        <input class="input" type="email" name="email" required>
        <span class="icon is-small is-left">
          <i class="fas fa-envelope"></i>
        </span>
      </div>
    </div>
    
    <div class="field">
      <div class="control">
        <button type="submit" class="button is-primary is-fullwidth">
          Reset Password
        </button>
      </div>
    </div>
    
    <div class="has-text-centered mt-4">
      <a href="{% url 'account_login' %}">Back to login</a>
    </div>
  </form>
</div>
```

### Custom Password Reset Done Page

```html
<!-- In password_reset_done.html -->
<div class="box">
  <div class="notification is-success">
    <h4 class="title is-5">Email Sent</h4>
    <p>We've sent you an email with a link to reset your password. Please check your inbox.</p>
  </div>
  
  <div class="content mt-4">
    <p>If you don't receive an email within a few minutes:</p>
    <ul>
      <li>Check your spam or junk folder</li>
      <li>Verify you entered the correct email address</li>
      <li>If you still need assistance, please <a href="{% url 'contact' %}">contact support</a></li>
    </ul>
  </div>
  
  <div class="has-text-centered mt-4">
    <a href="{% url 'account_login' %}" class="button is-light">
      Back to Login
    </a>
  </div>
</div>
```

## Advanced Customizations

### Custom Form Validation with Alpine.js

```html
<!-- In signup.html -->
<form x-data="{ 
  password: '', 
  confirmPassword: '',
  passwordMatch() { return this.password === this.confirmPassword },
  passwordStrength() {
    let score = 0;
    if (this.password.length > 7) score += 25;
    if (/[A-Z]/.test(this.password)) score += 25;
    if (/[0-9]/.test(this.password)) score += 25;
    if (/[^A-Za-z0-9]/.test(this.password)) score += 25;
    return score;
  }
}" method="post" action="{% url 'account_signup' %}">
  {% csrf_token %}
  
  <!-- Other form fields here -->
  
  <div class="field">
    <label class="label">Password</label>
    <div class="control">
      <input class="input" type="password" name="password1" x-model="password" required>
    </div>
    <div class="mt-2">
      <div class="strength-meter">
        <div class="strength-meter-fill" :style="'width: ' + passwordStrength() + '%'" 
             :class="{
               'is-danger': passwordStrength() < 50,
               'is-warning': passwordStrength() >= 50 && passwordStrength() < 75,
               'is-success': passwordStrength() >= 75
             }"></div>
      </div>
      <p class="help" x-text="
        passwordStrength() < 50 ? 'Weak password' : 
        passwordStrength() < 75 ? 'Good password' : 
        'Strong password'
      "></p>
    </div>
  </div>
  
  <div class="field">
    <label class="label">Confirm Password</label>
    <div class="control">
      <input class="input" :class="{ 'is-danger': !passwordMatch() && confirmPassword }" 
             type="password" name="password2" x-model="confirmPassword" required>
    </div>
    <p class="help is-danger" x-show="!passwordMatch() && confirmPassword">
      Passwords do not match
    </p>
  </div>
  
  <div class="field">
    <div class="control">
      <button type="submit" class="button is-primary is-fullwidth" 
              :disabled="!passwordMatch() || password.length < 8">
        Sign Up
      </button>
    </div>
  </div>
</form>

<style>
  .strength-meter {
    height: 5px;
    background-color: #e0e0e0;
    border-radius: 2px;
  }
  .strength-meter-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s ease;
  }
  .strength-meter-fill.is-danger {
    background-color: #f14668;
  }
  .strength-meter-fill.is-warning {
    background-color: #ffdd57;
  }
  .strength-meter-fill.is-success {
    background-color: #48c78e;
  }
</style>
```

### HTMX Real-time Username Availability

```html
<!-- In signup.html -->
<div class="field">
  <label class="label">Username</label>
  <div class="control">
    <input class="input" type="text" name="username" 
           hx-get="{% url 'check_username' %}" 
           hx-trigger="keyup changed delay:500ms" 
           hx-target="#username-availability">
  </div>
  <div id="username-availability"></div>
</div>
```

```html
<!-- In check_username.html (HTMX response) -->
{% if is_available %}
  <p class="help is-success">Username is available</p>
{% else %}
  <p class="help is-danger">Username is already taken</p>
{% endif %}
```

### HTMX Loading Indicator

```html
<!-- In base.html (add to head) -->
<style>
.htmx-indicator {
  opacity: 0;
  transition: opacity 500ms ease-in;
}
.htmx-request .htmx-indicator {
  opacity: 1;
}
.htmx-request.htmx-indicator {
  opacity: 1;
}
</style>

<!-- In any form with HTMX -->
<button type="submit" class="button is-primary">
  <span>Submit</span>
  <span class="icon htmx-indicator">
    <i class="fas fa-spinner fa-spin"></i>
  </span>
</button>
``` 