// ===============================
// SOCIALSPHERE MAIN.JS
// ===============================

// Fade in sections on scroll
const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = "1";
            entry.target.style.transform = "translateY(0)";
        }
    });
}, {
    threshold: 0.15
});

document.querySelectorAll("section").forEach((section) => {
    section.style.opacity = "0";
    section.style.transform = "translateY(60px)";
    section.style.transition = "all 0.8s ease";
    observer.observe(section);
});

// Animated counters
const counters = document.querySelectorAll(".stats h1");

counters.forEach(counter => {

    const target = counter.innerText;

    const number = parseInt(target.replace(/\D/g, ""));

    const suffix = target.replace(/[0-9]/g, "");

    let count = 0;

    const update = () => {

        count += Math.ceil(number / 80);

        if (count < number) {

            counter.innerText = count + suffix;

            requestAnimationFrame(update);

        } else {

            counter.innerText = target;

        }

    };

    update();

});

// Navbar background on scroll
const nav = document.querySelector("nav");

window.addEventListener("scroll", () => {

    if (window.scrollY > 80) {

        nav.style.background = "rgba(15,23,42,.95)";

        nav.style.boxShadow = "0 10px 30px rgba(0,0,0,.35)";

    } else {

        nav.style.background = "rgba(15,23,42,.75)";

        nav.style.boxShadow = "none";

    }

});

// Smooth scrolling
document.querySelectorAll('a[href^="#"]').forEach(anchor => {

    anchor.addEventListener("click", function(e){

        e.preventDefault();

        const target = document.querySelector(this.getAttribute("href"));

        if(target){

            target.scrollIntoView({

                behavior:"smooth"

            });

        }

    });

});

// Button click animation
document.querySelectorAll(".primary,.secondary,.signup-btn").forEach(btn=>{

    btn.addEventListener("click",()=>{

        btn.style.transform="scale(.96)";

        setTimeout(()=>{

            btn.style.transform="";

        },150);

    });

});

console.log("🚀 SocialSphere Loaded Successfully");