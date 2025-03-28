function register() {
    const form = document.getElementById('login-form');
    const data = new FormData(form);
    fetch('/register', {
        method: 'POST',
        body: data
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('message').textContent = data.message || data.error;
        if (data.message) form.reset();
    });
}

document.getElementById('login-form')?.addEventListener('submit', function(e) {
    e.preventDefault();
    const data = new FormData(this);
    fetch('/login', {
        method: 'POST',
        body: data
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            window.location.href = '/dashboard';
        } else {
            document.getElementById('message').textContent = data.error;
        }
    });
});

function logout() {
    fetch('/logout', { method: 'POST' })
    .then(response => response.json())
    .then(data => {
        if (data.message) window.location.href = '/';
    });
}

function negotiate(productName, productPrice) {
    const form = new FormData();
    form.append('product_name', productName);
    form.append('product_price', productPrice);
    fetch('/negotiate', {
        method: 'POST',
        body: form
    })
    .then(response => response.text())
    .then(html => {
        document.body.innerHTML = html;
    });
}

function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;
    const chatWindow = document.getElementById('chat-window');
    chatWindow.innerHTML += `<p>You: ${message}</p>`;
    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    })
    .then(response => response.json())
    .then(data => {
        chatWindow.innerHTML += `<p>Bot: ${data.response}</p>`;
        chatWindow.scrollTop = chatWindow.scrollHeight;
        input.value = '';
        if (data.response.startsWith('add_to_cart:')) {
            const negotiatedPrice = parseFloat(data.response.split(':')[1]);
            addToCart(productName, negotiatedPrice);
        } else if (data.response.includes('Negotiation has ended') || data.response.includes('Deal closed')) {
            input.disabled = true;
        }
    })
    .catch(error => {
        chatWindow.innerHTML += `<p>Error: ${error.message}</p>`;
    });
}

function addToCart(productName, negotiatedPrice) {
    fetch('/add_to_cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_name: productName, negotiated_price: negotiatedPrice })
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message || data.error);
        if (data.message) window.location.href = '/dashboard';
    });
}

function buyNow() {
    window.location.href = '/buy_now';
}

document.getElementById('payment-form')?.addEventListener('submit', function(e) {
    e.preventDefault();
    const data = new FormData(this);
    const paymentMethod = data.get('payment_method');
    
    // Show/hide payment details based on selection
    document.querySelectorAll('input[name="payment_method"]').forEach(radio => {
        radio.addEventListener('change', function() {
            document.getElementById('net_banking_details').style.display = this.value === 'net_banking' ? 'block' : 'none';
            document.getElementById('credit_card_details').style.display = this.value === 'credit_card' ? 'block' : 'none';
        });
    });

    fetch('/buy_now', {
        method: 'POST',
        body: data
    })
    .then(response => response.json())
    .then(data => {
        const resultDiv = document.getElementById('payment-result');
        if (data.message) {
            resultDiv.innerHTML = `<p>${data.message}</p>`;
            if (data.qr_code) {
                resultDiv.innerHTML += `<img src="data:image/png;base64,${data.qr_code}" alt="UPI QR Code">`;
            }
            setTimeout(() => window.location.href = '/dashboard', 3000);  // Redirect after 3 seconds
        } else {
            resultDiv.innerHTML = `<p>Error: ${data.error}</p>`;
        }
    });
});