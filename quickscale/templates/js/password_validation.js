/**
 * QuickScale Password Validation
 * 
 * This file provides client-side password validation functionality.
 * It checks password strength and matching confirmation.
 */

document.addEventListener('DOMContentLoaded', function() {
  // Get password input elements
  const passwordInput = document.querySelector('input[name="password1"]');
  const confirmInput = document.querySelector('input[name="password2"]');
  
  if (!passwordInput || !confirmInput) return;
  
  // Create password strength meter elements if they don't exist
  let strengthContainer = document.getElementById('password-strength-container');
  if (!strengthContainer) {
    strengthContainer = document.createElement('div');
    strengthContainer.id = 'password-strength-container';
    strengthContainer.innerHTML = `
      <div class="password-strength-meter mt-2">
        <div class="strength-meter-fill"></div>
      </div>
      <p class="help password-strength-text"></p>
    `;
    passwordInput.parentNode.appendChild(strengthContainer);
  }
  
  const strengthMeter = strengthContainer.querySelector('.strength-meter-fill');
  const strengthText = strengthContainer.querySelector('.password-strength-text');
  
  // Create confirmation message if it doesn't exist
  let confirmMessage = document.getElementById('password-match-message');
  if (!confirmMessage) {
    confirmMessage = document.createElement('p');
    confirmMessage.id = 'password-match-message';
    confirmMessage.className = 'help is-danger';
    confirmMessage.textContent = 'Passwords do not match';
    confirmMessage.style.display = 'none';
    confirmInput.parentNode.appendChild(confirmMessage);
  }
  
  // Get submit button
  const submitButton = document.querySelector('button[type="submit"]');
  
  // Function to check password strength
  function checkPasswordStrength(password) {
    let score = 0;
    
    // Check password length (minimum 8 characters)
    if (password.length >= 8) {
      score += 25;
    }
    
    // Check for uppercase letters
    if (/[A-Z]/.test(password)) {
      score += 25;
    }
    
    // Check for numbers
    if (/[0-9]/.test(password)) {
      score += 25;
    }
    
    // Check for special characters
    if (/[^A-Za-z0-9]/.test(password)) {
      score += 25;
    }
    
    return score;
  }
  
  // Function to update the UI
  function updateUI() {
    const password = passwordInput.value;
    const confirm = confirmInput.value;
    
    // Update strength meter
    const score = checkPasswordStrength(password);
    strengthMeter.style.width = `${score}%`;
    
    // Remove existing classes
    strengthMeter.classList.remove('is-danger', 'is-warning', 'is-success');
    
    // Add appropriate class based on score
    if (score < 50) {
      strengthMeter.classList.add('is-danger');
      strengthText.textContent = 'Weak password';
      strengthText.className = 'help is-danger';
    } else if (score < 75) {
      strengthMeter.classList.add('is-warning');
      strengthText.textContent = 'Good password';
      strengthText.className = 'help is-warning';
    } else {
      strengthMeter.classList.add('is-success');
      strengthText.textContent = 'Strong password';
      strengthText.className = 'help is-success';
    }
    
    // Check if passwords match
    if (confirm && password !== confirm) {
      confirmInput.classList.add('is-danger');
      confirmMessage.style.display = 'block';
    } else {
      confirmInput.classList.remove('is-danger');
      confirmMessage.style.display = 'none';
    }
    
    // Update submit button state if it exists
    if (submitButton) {
      const isValid = password.length >= 8 && (!confirm || password === confirm);
      submitButton.disabled = !isValid;
    }
  }
  
  // Add event listeners
  passwordInput.addEventListener('input', updateUI);
  confirmInput.addEventListener('input', updateUI);
  
  // Add CSS for strength meter
  const style = document.createElement('style');
  style.textContent = `
    .password-strength-meter {
      height: 5px;
      background-color: #e0e0e0;
      border-radius: 2px;
      margin-top: 5px;
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
  `;
  document.head.appendChild(style);
});

// Function to be called from HTMX to validate password
function validatePassword(password) {
  const score = (() => {
    let s = 0;
    if (password.length >= 8) s += 25;
    if (/[A-Z]/.test(password)) s += 25;
    if (/[0-9]/.test(password)) s += 25;
    if (/[^A-Za-z0-9]/.test(password)) s += 25;
    return s;
  })();
  
  let strengthClass = 'is-danger';
  let strengthText = 'Weak password';
  
  if (score >= 75) {
    strengthClass = 'is-success';
    strengthText = 'Strong password';
  } else if (score >= 50) {
    strengthClass = 'is-warning';
    strengthText = 'Good password';
  }
  
  const width = `${score}%`;
  
  return { score, strengthClass, strengthText, width };
} 