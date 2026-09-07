document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Sidebar Hamburger Menu Toggle
    const toggleBtn = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });

        // Close sidebar when tapping outside on mobile screens
        document.addEventListener('click', (e) => {
            if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target) && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
            }
        });
    }

    // 2. Micro-animation on Note Card Downloads
    const downloadButtons = document.querySelectorAll('.btn-download-circle');
    downloadButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            this.style.transform = 'scale(0.85)';
            setTimeout(() => {
                this.style.transform = '';
            }, 200);
        });
    });
});