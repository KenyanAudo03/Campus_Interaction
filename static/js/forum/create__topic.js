document.addEventListener('DOMContentLoaded', function() {
    const createOptions = document.querySelectorAll('.create__options a');
    const titleField = document.getElementById('title-field');
    const textPostFields = document.getElementById('text-post-fields');
    const imageVideoPostFields = document.getElementById('image-video-post-fields');
    const submitButtonDiv = document.getElementById('submit-button-div');
    const postForm = document.getElementById('post-form');

    let errorTimeout;

    function hideAllFields() {
        titleField.style.display = 'none';
        textPostFields.style.display = 'none';
        imageVideoPostFields.style.display = 'none';
        submitButtonDiv.style.display = 'none';

        createOptions.forEach(option => {
            option.classList.remove('active');
        });
    }

    function showTextPost(e) {
        e.preventDefault();
        hideAllFields();
        createOptions[0].classList.add('active');
        titleField.style.display = 'block';
        textPostFields.style.display = 'block';
        submitButtonDiv.style.display = 'block';
    }

    function showImageVideoPost(e) {
        e.preventDefault();
        hideAllFields();
        createOptions[1].classList.add('active');
        titleField.style.display = 'block';
        imageVideoPostFields.style.display = 'block';
        submitButtonDiv.style.display = 'block';
    }

    function showPollPost(e) {
        hideAllFields();
        createOptions[0].classList.add('active');
        titleField.style.display = 'block';
        textPostFields.style.display = 'block';
        submitButtonDiv.style.display = 'block';
    }

    createOptions[0].addEventListener('click', showTextPost);
    createOptions[1].addEventListener('click', showImageVideoPost);
    createOptions[2].addEventListener('click', showPollPost);

    showTextPost({ preventDefault: () => {}, target: createOptions[0] });

    const saveDraftBtn = document.getElementById('save-draft-btn');
    const publishBtn = document.getElementById('publish-btn');
    
    function submitPost(formData, loadingText, buttonText, forumId, isDraft) {
        const submitButton = postForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.textContent = loadingText;

        fetch(`/forums/${forumId}/create-post/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(text);
                });
            }
            return response.text();
        })
        .then(result => {
            if (isDraft) {
                window.location.href = `/forums/forum/${forumId}/drafts/`;
            } else {
                window.location.href = `/forums/${forumId}/`;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            displayError('An error occurred while posting. Please try again.');
        })
        .finally(() => {
            submitButton.disabled = false;
            submitButton.textContent = buttonText;
        });
    }

    function displayError(message) {
        const formErrorsDiv = document.createElement('div');
        formErrorsDiv.className = 'form-errors';
        formErrorsDiv.style.position = 'fixed';
        formErrorsDiv.style.bottom = '20px';
        formErrorsDiv.style.left = '50%';
        formErrorsDiv.style.transform = 'translateX(-50%)';
        formErrorsDiv.style.backgroundColor = '#ff3b30';
        formErrorsDiv.style.color = 'white';
        formErrorsDiv.style.padding = '12px 20px';
        formErrorsDiv.style.borderRadius = '7px';
        formErrorsDiv.style.fontSize = '16px';
        formErrorsDiv.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.1)';
        formErrorsDiv.style.zIndex = '9999';
        formErrorsDiv.innerHTML = message;
        document.body.appendChild(formErrorsDiv);

        if (errorTimeout) {
            clearTimeout(errorTimeout);
        }

        errorTimeout = setTimeout(() => {
            formErrorsDiv.style.display = 'none';
        }, 5000);
    }

    postForm.addEventListener('submit', function(e) {
        e.preventDefault();
    });

    function handleSubmit(isDraft) {
        const title = postForm.querySelector('input[name="title"]');
        const content = postForm.querySelector('textarea[name="content"]');
        const image = postForm.querySelector('input[name="image"]');
        const video = postForm.querySelector('input[name="video"]');
        const errors = [];
        const forumId = document.querySelector('[data-forum-id]').getAttribute('data-forum-id');

        if (!title.value.trim()) {
            displayError('Title is required.');
            return;
        }

        if (createOptions[0].classList.contains('active') && !content.value.trim()) {
            displayError('Content is required for text posts.');
            return;
        }

        if (createOptions[1].classList.contains('active') && !(image.files.length || video.files.length)) {
            displayError('Image or Video is required for image/video posts.');
            return;
        }

        const formData = new FormData(postForm);
        formData.append('is_draft', isDraft.toString());
        submitPost(formData, isDraft ? 'Saving Draft...' : 'Posting...', isDraft ? 'Save Draft' : 'Approve & Post', forumId, isDraft);
    }

    saveDraftBtn.addEventListener('click', function() {
        handleSubmit(true);  
    });

    publishBtn.addEventListener('click', function() {
        handleSubmit(false);  
    });
});
