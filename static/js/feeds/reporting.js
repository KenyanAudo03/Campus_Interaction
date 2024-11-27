function submitReport(event) {
    event.preventDefault();
    const form = event.target;
    const postId = document.getElementById('reportPostId').value;
    const formData = new FormData(form);
    
    fetch(`/feeds/post/${postId}/report/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCsrfToken(),
            "Content-Type": "application/json",
        },
        body: JSON.stringify(Object.fromEntries(formData)),
    })
    .then((response) => response.json())
    .then((data) => {
        if (data.success) {
            const reportModal = bootstrap.Modal.getInstance(document.getElementById('reportModal'));
            reportModal.hide();
            form.reset();
            Swal.fire({
                icon: 'success',
                title: 'Thank You',
                text: 'Your report has been submitted.',
                timer: 2000,
                showConfirmButton: false
            });
        } else {
            throw new Error(data.errors || 'Failed to submit report');
        }
    })
    .catch((error) => {
        console.error("Error:", error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Failed to submit report.'
        });
    });
}

function reportPost(postId) {
    document.getElementById('reportPostId').value = postId;
    
    const reportModal = new bootstrap.Modal(document.getElementById('reportModal'));
    reportModal.show();
} 