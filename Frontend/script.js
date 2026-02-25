// No JavaScript required for this UI
// Hover animation is handled fully by CSS


console.log("Dashboard loaded");

// Later:
// fetch("/api/dashboard-data")
// .then(res => res.json())
// .then(data => updateUI(data));

/* ===============================
   CATEGORY / SUB-WALLET LOGIC
   =============================== */

document.addEventListener("DOMContentLoaded", () => {

  /* ADD CATEGORY ELEMENTS */
  const addCategoryBtn = document.querySelector(".add-category-btn");
  const categoryModal = document.getElementById("categoryModal");
  const cancelBtn = document.getElementById("cancelBtn");
  const confirmBtn = document.getElementById("addBtn");

  const categoryNameInput = document.getElementById("categoryName");
  const categoryEmojiInput = document.getElementById("categoryEmoji");
  const categoryAmountInput = document.getElementById("categoryAmount");

  const accountsContainer = document.querySelector(".accounts");

  /* DISCARD MODAL ELEMENTS */
  const discardModal = document.getElementById("discardModal");
  const discardCancel = document.getElementById("discardCancel");
  const discardConfirm = document.getElementById("discardConfirm");

  let selectedCategory = null;

  /* -------------------------------
     OPEN ADD CATEGORY MODAL
  -------------------------------- */
  addCategoryBtn.addEventListener("click", () => {
    categoryModal.style.display = "flex";
  });

  cancelBtn.addEventListener("click", closeAddModal);

  confirmBtn.addEventListener("click", () => {
    const name = categoryNameInput.value.trim();
    const emoji = categoryEmojiInput.value.trim();
    const amount = categoryAmountInput.value.trim();

    if (!name || !emoji || !amount) {
      alert("Please fill all fields");
      return;
    }

    const accountDiv = document.createElement("div");
    accountDiv.className = "account";
    accountDiv.dataset.amount = amount; // store amount safely

    accountDiv.innerHTML = `
      <div class="left">
        <span class="icon">${emoji}</span> ${name}
      </div>
      <div class="right">₹${amount} ›</div>
    `;

    /* CLICK CATEGORY → OPEN DISCARD MODAL */
    accountDiv.addEventListener("click", () => {
      selectedCategory = accountDiv;
      discardModal.style.display = "flex";
    });

    accountsContainer.appendChild(accountDiv);
    closeAddModal();
  });

  /* -------------------------------
     DISCARD CATEGORY
  -------------------------------- */
  discardCancel.addEventListener("click", () => {
    discardModal.style.display = "none";
    selectedCategory = null;
  });

  discardConfirm.addEventListener("click", () => {
    if (selectedCategory) {
      /* FUTURE LOGIC:
         add selectedCategory.dataset.amount to main balance
      */
      selectedCategory.remove();
    }

    discardModal.style.display = "none";
    selectedCategory = null;
  });

  /* -------------------------------
     HELPERS
  -------------------------------- */
  function closeAddModal() {
    categoryModal.style.display = "none";
    categoryNameInput.value = "";
    categoryEmojiInput.value = "";
    categoryAmountInput.value = "";
  }

});