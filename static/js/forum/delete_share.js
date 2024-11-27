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

function sharePost(postId) {
  const url = `${window.location.origin}/posts/${postId}`;
  copyToClipboard(url);
}
function deletePost(postId) {
  // Show the custom MDB confirmation modal
  $("#deletePostModal").modal("show");

  // When the user clicks "Delete" in the modal
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
          console.log(data); // Log the server response for debugging
          if (data.status === "success") {
            // Remove the post from the DOM
            $(`#post-${postId}`).fadeOut(300, function () {
              $(this).remove();
            });

            // Update the post count in the header from the server's response
            $(".content-header h2").text(`${data.post_count} Topics`); // Use the post_count from the server
            $(".topics-count")
              .text(`${data.post_count} `)
              .append("<span>Topics</span>");

            showNotification("Post deleted successfully");
          } else {
            showNotification(data.message, "error");
          }
        },
        error: function (xhr, status, error) {
          showNotification("Failed to delete post", "error");
        },
      });

      // Close the modal after the deletion is confirmed
      $("#deletePostModal").modal("hide");
    });

  // Close the modal when clicking "Cancel"
  $("#deletePostModal").on("hidden.bs.modal", function () {
    $("#confirmDeleteBtn").off("click"); // Remove previous event handler to avoid multiple triggers
  });
}

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
