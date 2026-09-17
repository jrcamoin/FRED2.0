const header = document.querySelector('.site-header');
const menuButton = document.querySelector('.menu-button');
menuButton.addEventListener('click', () => {
  const isOpen = header.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(isOpen));
  menuButton.setAttribute('aria-label', isOpen ? 'Close menu' : 'Open menu');
});
document.querySelectorAll('nav a').forEach(link => link.addEventListener('click', () => {
  header.classList.remove('open');
  menuButton.setAttribute('aria-expanded', 'false');
  menuButton.setAttribute('aria-label', 'Open menu');
}));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && header.classList.contains('open')) {
    header.classList.remove('open');
    menuButton.setAttribute('aria-expanded', 'false');
    menuButton.setAttribute('aria-label', 'Open menu');
    menuButton.focus();
  }
});
document.getElementById('year').textContent = new Date().getFullYear();

const inquiryForm = document.getElementById('inquiry-form');
const draft = document.getElementById('inquiry-draft');
const status = document.getElementById('form-status');
inquiryForm.addEventListener('submit', event => {
  event.preventDefault();
  const audience = document.getElementById('audience').value;
  const inquiry = document.getElementById('inquiry');
  if (!inquiry.value.trim()) {
    inquiry.setCustomValidity('Please tell us a little about your interest.');
    inquiry.reportValidity();
    return;
  }
  draft.value = `Hello Jacob,\n\nI’m reaching out as a ${audience.toLowerCase()} about Human Frame Robotics.\n\n${inquiry.value.trim()}\n\nBest,\n`;
  document.getElementById('inquiry-result').hidden = false;
  status.textContent = 'Your email app should open with a draft. If it doesn’t, copy this inquiry and email jacobcamoin@yahoo.com. Nothing has been sent by this website.';
  window.location.href = `mailto:jacobcamoin@yahoo.com?subject=${encodeURIComponent(`Human Frame Robotics inquiry — ${audience}`)}&body=${encodeURIComponent(draft.value)}`;
});
document.getElementById('inquiry').addEventListener('input', event => event.target.setCustomValidity(''));
document.getElementById('copy-inquiry').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(draft.value);
    status.textContent = 'Copied. Paste into an email to jacobcamoin@yahoo.com.';
  } catch {
    draft.focus();
    draft.select();
    status.textContent = 'Select and copy the inquiry above, then email jacobcamoin@yahoo.com.';
  }
});
