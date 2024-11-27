// Modal functionality
document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("imageModal");
  const modalImage = document.getElementById("modalImage");
  const closeBtn = modal.querySelector(".close-btn");
  const downloadBtn = modal.querySelector(".download-btn");
  const prevBtn = modal.querySelector(".prev-btn");
  const nextBtn = modal.querySelector(".next-btn");
  const overlay = modal.querySelector(".modal-overlay");

  let currentImageIndex = 0;
  let images = [];

  // Function to open modal
  function openModal(imgSrc, index) {
    modal.classList.add("active");
    modalImage.src = imgSrc;
    currentImageIndex = index;
    document.body.style.overflow = "hidden";
    updateNavigationButtons();
  }

  // Function to close modal
  function closeModal() {
    modal.classList.remove("active");
    modalImage.src = "";
    document.body.style.overflow = "";
  }

  // Function to update navigation buttons
  function updateNavigationButtons() {
    prevBtn.style.display = currentImageIndex > 0 ? "flex" : "none";
    nextBtn.style.display =
      currentImageIndex < images.length - 1 ? "flex" : "none";
  }

  // Function to navigate to previous image
  function showPreviousImage() {
    if (currentImageIndex > 0) {
      currentImageIndex--;
      modalImage.src = images[currentImageIndex].src;
      updateNavigationButtons();
    }
  }

  // Function to navigate to next image
  function showNextImage() {
    if (currentImageIndex < images.length - 1) {
      currentImageIndex++;
      modalImage.src = images[currentImageIndex].src;
      updateNavigationButtons();
    }
  }

  // Function to download image
  function downloadImage() {
    const link = document.createElement("a");
    link.href = modalImage.src;
    link.download = "image.jpg";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // Collect all post images
  function initializeImages() {
    images = Array.from(document.querySelectorAll(".post-content img"));

    // Add click listeners to all images
    images.forEach((img, index) => {
      img.addEventListener("click", () => openModal(img.src, index));
    });
  }

  // Event listeners
  closeBtn.addEventListener("click", closeModal);
  overlay.addEventListener("click", closeModal);
  downloadBtn.addEventListener("click", downloadImage);
  prevBtn.addEventListener("click", showPreviousImage);
  nextBtn.addEventListener("click", showNextImage);

  // Keyboard navigation
  document.addEventListener("keydown", (e) => {
    if (!modal.classList.contains("active")) return;

    switch (e.key) {
      case "ArrowLeft":
        showPreviousImage();
        break;
      case "ArrowRight":
        showNextImage();
        break;
      case "Escape":
        closeModal();
        break;
    }
  });

  // Initialize
  initializeImages();
});


// Like Post and Posting
document.addEventListener('DOMContentLoaded', function () {
  const postForm = document.getElementById('post-form');
  const postContainer = document.querySelector('.main-content');
  const postCountElement = document.getElementById('topics-count');

  function showErrorNotification(message) {
    const notification = document.createElement('div');
    notification.classList.add('error-notification');
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.style.opacity = 1;
    }, 0);

    setTimeout(() => {
      notification.style.opacity = 0;
      setTimeout(() => {
        notification.remove();
      }, 500);
    }, 4000);
  }

  function makeLinksClickable(postContent) {
    const urlRegex = /https?:\/\/[^\s]+/g;
    return postContent.replace(urlRegex, function (url) {
      return `<a href="${url}" target="_blank">${url}</a>`;
    });
  }

  async function toggleLike(postId) {
    const likeElement = document.querySelector(`#post-${postId} .stat-item.likes`);
    const likeIcon = likeElement.querySelector("i");
    const likeCountElement = likeElement.querySelector("span");

    try {
      const response = await fetch(`/forums/post/${postId}/like/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
          "Content-Type": "application/json",
        },
      });

      const data = await response.json();

      if (response.ok) {
        likeCountElement.textContent = data.like_count;

        if (data.status === "liked") {
          likeIcon.classList.add("liked");
        } else {
          likeIcon.classList.remove("liked");
        }
      } else {
        console.error("Failed to toggle like:", data);
      }
    } catch (error) {
      console.error("Error:", error);
    }
  }

  function toggleMenu(postId) {
    const menu = document.getElementById(`menu-${postId}`);
    menu.classList.toggle('show');
  }

  async function deletePost(postId) {
    try {
      const response = await fetch(`/forums/post/${postId}/delete/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
        },
      });

      const data = await response.json();

      if (response.ok) {
        const postElement = document.getElementById(`post-${postId}`);
        if (postElement) {
          postElement.remove();
        }

        updateTopicCount();
      } else {
        console.error("Failed to delete post:", data);
        alert(data.message || "Failed to delete the post");
      }
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred while deleting the post");
    }
  }

  function sharePost(postId) {
    console.log('Share post', postId);
    alert('Share functionality coming soon!');
  }

  function updateTopicCount() {
    fetch('/forums/get_topic_count/')
      .then(response => response.json())
      .then(data => {
        if (data.post_count !== undefined) {
          postCountElement.querySelector('span').textContent = data.post_count;
        }
      })
      .catch(error => {
        console.error('Error fetching topic count:', error);
      });
  }

  postForm.addEventListener('submit', function (e) {
    e.preventDefault();

    const formData = new FormData(postForm);
    const video = formData.get('video');
    const forumId = document.getElementById('post-form-container').dataset.forumId;

    if (video && video.size > 10 * 1024 * 1024) {
      showErrorNotification("Video file size must not exceed 10MB.");
      return;
    }

    fetch(`/forums/${forumId}/create_post/`, {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
      }
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'posted') {
          const newPostArticle = document.createElement('article');
          newPostArticle.classList.add('post');
          newPostArticle.id = `post-${data.post_id}`;

          const postContent = makeLinksClickable(data.content);

          newPostArticle.innerHTML = `
            <div class="author__options">
              <div class="post-author">
                <img src="${data.user_profile_pic}" alt="${data.username} Profile" />
                <div class="author-details">
                  <div class="author-name">${data.username}</div>
                  <div class="post-meta">
                    <span class="user-role">${data.user_role}</span>
                    <span class="separator">•</span>
                    <span class="publish-info">Published in ${data.forum_name}</span>
                  </div>
                </div>
              </div>
              <div class="post-options">
                <button class="options-btn" onclick="toggleMenu('${data.post_id}')">
                  <i class="fa-solid fa-ellipsis-vertical"></i>
                </button>
                <div class="options-menu" id="menu-${data.post_id}">
                  ${data.user_can_delete ? `
                    <button class="menu-item delete-btn" onclick="deletePost('${data.post_id}')">
                      Delete
                    </button>
                  ` : ''}
                  <button class="menu-item" onclick="sharePost(${data.post_id})">
                    Share
                  </button>
                </div>
              </div>
            </div>

            <div class="post-content">
              <p>${postContent}</p>
              ${data.media_url ? `
                <div class="media-container">
                  ${data.media_url.includes('.mp4') ? `
                    <video class="video-js vjs-default-skin" controls preload="auto" style="width: 100%; height: 350px; object-fit: cover;">
                      <source src="${data.media_url}" type="video/mp4" />
                    </video>
                  ` : `
                    <img src="${data.media_url}" alt="Post media" style="width: 100%; height: auto;" />
                  `}
                </div>
              ` : ''}
            </div>

            <div class="post-stats">
              <span class="stat-item likes" onclick="toggleLike('${data.post_id}')">
                <i class="fa-solid fa-thumbs-up ${data.is_liked ? 'liked' : ''}"></i>
                <span>${data.likes_count}</span>
              </span>
              <span class="stat-item">
                <i class="fa-regular fa-eye"></i>
                <span>${data.views_count}</span>
              </span>
              <span class="stat-item">
                <i class="fa-solid fa-comment"></i>
                <span>0</span>
              </span>
              <span class="post-time" style="margin-left: 10px">Just now</span>
            </div>
          `;

          postContainer.insertBefore(newPostArticle, postContainer.querySelector('article'));

          updateTopicCount(); // Ensure that this function updates the post count after adding the new post

          postForm.reset();
        }
      })
      .catch(error => {
        console.error('Error:', error);
        alert('Failed to post. Please try again.');
      });
  });

  document.addEventListener('click', function (e) {
    if (e.target.closest('.stat-item.likes')) {
      const postId = e.target.closest('.post').id.replace('post-', '');
      toggleLike(postId);
    }

    if (e.target.closest('.options-btn')) {
      const postId = e.target.closest('.post').id.replace('post-', '');
      toggleMenu(postId);
    }
  });
});



// JavaScript to handle switching between image and video input, ensuring only one media type can be uploaded at a time.
document.addEventListener('DOMContentLoaded', function () {
  const imageField = document.querySelector('.image-field');
  const videoField = document.querySelector('.video-field');
  const imageInput = document.querySelector('input[name="image"]');
  const videoInput = document.querySelector('input[name="video"]');
  const messageContainer = document.createElement('div');
  document.body.appendChild(messageContainer);

  function showMessage(message) {
      messageContainer.textContent = message;
      messageContainer.style.position = 'fixed';
      messageContainer.style.bottom = '10px';
      messageContainer.style.left = '50%';
      messageContainer.style.transform = 'translateX(-50%)';
      messageContainer.style.padding = '10px';
      messageContainer.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
      messageContainer.style.color = 'white';
      messageContainer.style.borderRadius = '5px';
      messageContainer.style.fontSize = '14px';
      messageContainer.style.opacity = '1';
      messageContainer.style.transition = 'opacity 0.5s ease-out'; // Transition for fade-out

      setTimeout(() => {
          messageContainer.style.opacity = '0';
          setTimeout(() => {
              messageContainer.textContent = ''; 
          }, 500); 
      }, 3000); 
  }

  imageInput.addEventListener('change', function () {
      if (videoInput.files.length > 0) {
          videoInput.value = '';
          showMessage('Video file removed. Only one file (image or video) can be submitted.');
      }
  });

  videoInput.addEventListener('change', function () {
      if (imageInput.files.length > 0) {
          imageInput.value = '';
          showMessage('Image file removed. Only one file (image or video) can be submitted.');
      }

      const videoFile = videoInput.files[0];
      if (videoFile && videoFile.type !== 'video/mp4') {
          showMessage('Please upload a .mp4 video file.');
          videoInput.value = '';
      }
  });
});

