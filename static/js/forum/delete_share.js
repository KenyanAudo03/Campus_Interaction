// Show Post Option menu
function toggleMenu(postId) {
  const menu = document.getElementById(`menu-${postId}`);
  const isDisplayed = menu.style.display === "block";

  document.querySelectorAll(".options-menu").forEach((m) => {
    if (m !== menu) m.style.display = "none";
  });

  menu.style.display = isDisplayed ? "none" : "block";

  if (!isDisplayed) {
    setTimeout(() => {
      function handleOutsideClick(event) {
        if (
          !menu.contains(event.target) &&
          !event.target.closest(".options-btn")
        ) {
          menu.style.display = "none";
          document.removeEventListener("click", handleOutsideClick);
        }
      }

      document.addEventListener("click", handleOutsideClick);
    }, 0);
  }
}

// Copy the Links for posts during share
function copyToClipboard(text, postId) {
  const menu = document.querySelector(".options-menu");

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        showNotification("Post link copied to clipboard!");
        menu.style.display = "none";
      })
      .catch((err) => {
        console.error("Failed to copy the link:", err);
        fallbackCopyText(text);
        menu.style.display = "none";
      });
  } else {
    fallbackCopyText(text);
    menu.style.display = "none";
  }
}

function fallbackCopyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);

  textarea.select();
  textarea.setSelectionRange(0, text.length);

  try {
    document.execCommand("copy");
    showNotification("Post link copied to clipboard!");
  } catch (err) {
    console.error("Fallback: Failed to copy text:", err);
    showNotification("Unable to copy the link", "error");
  }

  document.body.removeChild(textarea);
}

// share posts
function sharePost(postId) {
  const forumId = document
    .querySelector("[data-forum-id]")
    .getAttribute("data-forum-id");
  const url = `${window.location.origin}/forums/forum/${forumId}/post/${postId}`;
  copyToClipboard(url);
}

// Download Video/Images
window.onload = function () {
  const postContext = $(".pageContext").data("post-context");

  window.deletePost = function (postId) {
    $("#deletePostModal").modal("show");

    $("#confirmDeleteBtn")
      .off("click")
      .on("click", function () {
        $.ajax({
          url: `/forums/post/${postId}/delete/`,
          type: "DELETE",
          headers: {
            "X-CSRFToken": getCsrfToken(),
          },
          dataType: "json",
          success: function (data) {
            if (data.status === "success") {
              if (postContext === "post_detail") {
                window.location.href = `/forums/${data.forum_id}/`;
              } else if (postContext === "forum_detail") {
                $(`#post-${postId}`).fadeOut(300, function () {
                  $(this).remove();
                });
                $(".content-header h2").text(`${data.post_count} Topics`);
                $(".topics-count")
                  .text(`${data.post_count} `)
                  .append("<span>Topics</span>");
                showNotification("Post deleted successfully");
              }
            } else {
              showNotification(data.message, "error");
            }
          },
          error: function () {
            showNotification("Failed to delete post", "error");
          },
        });

        $("#deletePostModal").modal("hide");
      });

    $("#deletePostModal").on("hidden.bs.modal", function () {
      $("#confirmDeleteBtn").off("click");
    });
  };
};

function getCsrfToken() {
  return $('input[name="csrfmiddlewaretoken"]').val();
}

function showNotification(message, type = "info") {
  const existingNotifications = document.querySelectorAll(".notification");
  existingNotifications.forEach((notify) => notify.remove());

  const notification = document.createElement("div");
  notification.className = `notification ${type}`;
  notification.textContent = message;

  notification.style.cssText = `
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background-color: ${type === "error" ? "#f44336" : "#4CAF50"};
    color: white;
    padding: 12px 24px;
    border-radius: 4px;
    z-index: 1000;
    opacity: 0;
    transition: opacity 0.3s ease-in-out;
  `;

  document.body.appendChild(notification);
  notification.offsetHeight;
  notification.style.opacity = "1";

  setTimeout(() => {
    notification.style.opacity = "0";
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

document.addEventListener("DOMContentLoaded", () => {
  // Function to generate a random filename starting with camphub
  function generateRandomFilename(type) {
    const randomString = Math.random().toString(36).substring(2, 10);
    return `camphub_${type}_${randomString}`;
  }

  // Add event listeners to all download buttons
  function attachDownloadListeners() {
    const downloadButtons = document.querySelectorAll(".download-media-btn");

    downloadButtons.forEach((saveButton) => {
      saveButton.addEventListener("click", (event) => {
        // Find the closest post container to ensure we're in the right context
        const postContainer = event.target.closest(".post");

        if (!postContainer) {
          console.error("Could not find post container");
          return;
        }

        // Find media container within the specific post
        const mediaContainer = postContainer.querySelector(".media-container");

        if (!mediaContainer) {
          console.error("No media container found in this post");
          alert("No media found to download.");
          return;
        }

        let downloadUrl = "";
        let fileName = "";

        // Check for image
        const image = mediaContainer.querySelector("img");
        if (image) {
          downloadUrl = image.src;
          fileName = generateRandomFilename("image") + ".jpg";
        }

        // Check for video
        const video = mediaContainer.querySelector("video");
        if (video) {
          const source = video.querySelector("source");
          if (source) {
            downloadUrl = source.src;
            fileName = generateRandomFilename("video") + ".mp4";
          }
        }

        // If media found, trigger download
        if (downloadUrl) {
          fetch(downloadUrl)
            .then((response) => {
              if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
              }
              return response.blob();
            })
            .then((blob) => {
              // Create a temporary anchor element to trigger download
              const link = document.createElement("a");
              link.href = URL.createObjectURL(blob);
              link.download = fileName;
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
            })
            .catch((error) => {
              console.error("Download failed:", error);
              alert("Failed to download the media file. " + error.message);
            });
        } else {
          alert("No media found to download.");
        }
      });
    });
  }

  // Initial attachment of listeners
  attachDownloadListeners();

  // Optional: If you're using dynamic content loading,
  // you might want to re-attach listeners after content changes
  // This is a placeholder for such a mechanism
  // window.addEventListener('contentLoaded', attachDownloadListeners);
});
