// GSAP scroll & entry animations
gsap.registerPlugin(ScrollTrigger);

// Hero entrance
gsap.from('.hero-text > *', {
  y: 40, opacity: 0, duration: 1, ease: 'power3.out', stagger: 0.12, delay: 0.2
});
gsap.from('#ladyJustice', { x: -60, opacity: 0, duration: 1.2, ease: 'power3.out', delay: 0.1 });
gsap.from('#navbar', { y: -40, opacity: 0, duration: 0.9, ease: 'power3.out' });

// Reveal on scroll
gsap.utils.toArray('.reveal').forEach((el) => {
  gsap.to(el, {
    y: 0, opacity: 1, duration: 1, ease: 'power3.out',
    scrollTrigger: { trigger: el, start: 'top 85%' }
  });
});

// Subtle parallax on hero image
gsap.to('#ladyJustice', {
  yPercent: -10,
  ease: 'none',
  scrollTrigger: { trigger: 'body', start: 'top top', end: '+=600', scrub: true }
});
