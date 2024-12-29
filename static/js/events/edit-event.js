document.addEventListener('DOMContentLoaded', function() {
    const editEventForm = document.getElementById('editEventForm');
    const saveEventChangesBtn = document.getElementById('saveEventChangesBtn');
    
    if (editEventForm) {
        editEventForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const eventId = document.getElementById('event-container').getAttribute('data-event-id');
            const formData = new FormData(this);
            const jsonPayload = {};

            for (let [key, value] of formData.entries()) {
                if (value || value === 0) {
                    jsonPayload[key] = value;
                }
            }

            const checkboxes = this.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                if (checkbox.name) {
                    jsonPayload[checkbox.name] = checkbox.checked;
                }
            });

            if (Object.keys(jsonPayload).length === 0) {
                Swal.fire({
                    icon: 'warning',
                    title: 'No Changes',
                    text: 'Please make some changes before submitting.',
                    confirmButtonColor: '#3085d6'
                });
                return;
            }

            const payloadString = JSON.stringify(jsonPayload);
            formData.append('payload', payloadString);

            saveEventChangesBtn.disabled = true;
            saveEventChangesBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...';

            fetch(`/events/api/events/${eventId}/update/`, {
                method: 'PATCH',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    throw new Error(data.error || 'Update failed');
                }

                Swal.fire({
                    icon: 'success',
                    title: 'Event Updated',
                    text: data.message || 'Event updated successfully',
                    confirmButtonColor: '#3085d6'
                }).then(() => {
                    location.reload();
                });
            })
            .catch(error => {
                Swal.fire({
                    icon: 'error',
                    title: 'Update Failed',
                    text: error.message || 'There was an error updating the event. Please try again.',
                    confirmButtonColor: '#d33'
                });
            })
            .finally(() => {
                saveEventChangesBtn.disabled = false;
                saveEventChangesBtn.innerHTML = 'Save Changes';
            });
        });
    } else {
        console.error('Edit Event Form not found!');
    }
});