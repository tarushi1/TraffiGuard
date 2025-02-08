document.getElementById("emergency-form").addEventListener("submit", function(event) {
    event.preventDefault();
    
    const vehicle = document.getElementById("vehicle").value;
    const location = document.getElementById("location").value;
    const priority = document.getElementById("priority").value;

    if (vehicle && location && priority) {
        alert("Emergency submitted successfully!");
        this.reset(); // Clear form after submission
    } else {
        alert("Please fill all fields.");
    }
});
