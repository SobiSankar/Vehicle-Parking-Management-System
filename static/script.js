document.querySelectorAll('.flash').forEach((el) => {
    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transition = 'opacity 0.3s ease';
    }, 3000);
});
