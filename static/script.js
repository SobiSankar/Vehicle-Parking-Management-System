(() => {
  const form = document.getElementById('vehicle-entry-form');
  if (!form) return;

  form.addEventListener('submit', (event) => {
    const vehicleNumber = form.querySelector('input[name="vehicle_number"]').value.trim();
    const ownerName = form.querySelector('input[name="owner_name"]').value.trim();
    const contact = form.querySelector('input[name="contact_number"]').value.trim();
    const vehicleType = form.querySelector('select[name="vehicle_type"]').value.trim();

    if (!vehicleNumber || !ownerName || !contact || !vehicleType) {
      event.preventDefault();
      alert('Please fill all required fields.');
      return;
    }

    if (!/^\d{10}$/.test(contact)) {
      event.preventDefault();
      alert('Contact number must be 10 digits.');
    }
  });
})();
