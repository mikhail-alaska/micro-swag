const button = document.querySelector('#button');
const result = document.querySelector('#result');

button.onclick = async () => {
  button.disabled = true;
  result.textContent = 'Ждём CVE…';
  try {
    const response = await fetch('/api/click', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        language: navigator.language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        platform: navigator.platform,
        screen_width: screen.width,
        screen_height: screen.height,
        hardware_concurrency: navigator.hardwareConcurrency,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Не получилось получить CVE');
    result.textContent = `${data.message}\n\n${data.cve.id}\n${data.cve.description || 'Без описания'}\n\nCVSS: ${data.cve.cvss_score ?? 'нет оценки'}`;
  } catch (error) {
    result.textContent = `Ошибка: ${error.message}`;
  } finally {
    button.disabled = false;
  }
};
