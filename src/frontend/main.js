const progressBar = document.getElementById("progressBar");
const confidenceValue = document.getElementById("confidenceValue");

if (progressBar && confidenceValue) {
  const values = [86, 88, 84, 91, 87];
  let index = 0;

  setInterval(() => {
    index = (index + 1) % values.length;
    const next = values[index];
    progressBar.style.width = `${next}%`;
    confidenceValue.textContent = `${next}%`;
  }, 2800);
}
