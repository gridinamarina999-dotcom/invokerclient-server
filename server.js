const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const nodemailer = require('nodemailer');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());
app.use(express.static('./public'));

const DATA_DIR = './data';
const USERS_FILE = path.join(DATA_DIR, 'users.json');

if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR);
}

// Инициализация админа
function initializeAdmin() {
    let users = [];
    if (fs.existsSync(USERS_FILE)) {
        try {
            users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
        } catch (e) {
            users = [];
        }
    }

    // Проверяем если админа нет - создаем
    const adminEmail = 'gridinamarina999@gmail.com';
    const adminPassword = Buffer.from('q1w2e3334').toString('base64');
    
    if (!users.some(u => u.email === adminEmail)) {
        const admin = {
            id: Date.now(),
            name: 'Admin',
            email: adminEmail,
            password: adminPassword,
            registeredAt: new Date().toLocaleString('ru-RU'),
            lastLogin: null,
            isAdmin: true
        };
        users.push(admin);
        fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
        console.log('✅ Админ-аккаунт создан!');
        console.log('📧 Email: gridinamarina999@gmail.com');
        console.log('🔐 Пароль: q1w2e3334');
    }
}

initializeAdmin();

if (!fs.existsSync(USERS_FILE)) {
    fs.writeFileSync(USERS_FILE, JSON.stringify([], null, 2));
}

// Email конфиг
const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
        user: process.env.EMAIL_USER || 'your-email@gmail.com',
        pass: process.env.EMAIL_PASS || 'your-app-password'
    }
});

function getUsers() {
    try {
        const data = fs.readFileSync(USERS_FILE, 'utf8');
        return JSON.parse(data);
    } catch (error) {
        return [];
    }
}

function saveUsers(users) {
    try {
        fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
        return true;
    } catch (error) {
        return false;
    }
}

// РЕГИСТРАЦИЯ
app.post('/api/auth/signup', async (req, res) => {
    const { name, email, password, confirmPassword } = req.body;

    if (!name || !email || !password || !confirmPassword) {
        return res.status(400).json({ success: false, error: 'Все поля обязательны' });
    }

    if (password !== confirmPassword) {
        return res.status(400).json({ success: false, error: 'Пароли не совпадают' });
    }

    if (password.length < 6) {
        return res.status(400).json({ success: false, error: 'Пароль минимум 6 символов' });
    }

    const users = getUsers();

    if (users.some(u => u.email === email)) {
        return res.status(400).json({ success: false, error: 'Email уже зарегистрирован' });
    }

    const newUser = {
        id: Date.now(),
        name,
        email,
        password: Buffer.from(password).toString('base64'),
        registeredAt: new Date().toLocaleString('ru-RU'),
        lastLogin: null,
        isAdmin: false // Обычные пользователи не админы
    };

    users.push(newUser);

    if (saveUsers(users)) {
        // Отправляем email
        try {
            await transporter.sendMail({
                from: process.env.EMAIL_USER || 'noreply@invokerclient.com',
                to: email,
                subject: 'Добро пожаловать в InvokerClient!',
                html: `
                    <h2>Спасибо за регистрацию!</h2>
                    <p>Привет, ${name}!</p>
                    <p>Ваш аккаунт успешно создан.</p>
                    <p><strong>Email:</strong> ${email}</p>
                    <p>Теперь вы можете использовать все возможности InvokerClient!</p>
                    <p><a href="https://invokerclient.up.railway.app">Перейти на сайт</a></p>
                `
            });
        } catch (emailError) {
            console.log('Email не отправлен (это нормально в разработке):', emailError.message);
        }

        res.status(201).json({ 
            success: true,
            message: 'Регистрация успешна!',
            user: { id: newUser.id, name: newUser.name, email: newUser.email, isAdmin: newUser.isAdmin }
        });
    } else {
        res.status(500).json({ success: false, error: 'Ошибка сохранения' });
    }
});

// ВХОД
app.post('/api/auth/login', (req, res) => {
    const { email, password } = req.body;

    if (!email || !password) {
        return res.status(400).json({ success: false, error: 'Email и пароль обязательны' });
    }

    const users = getUsers();
    const encodedPassword = Buffer.from(password).toString('base64');
    const user = users.find(u => u.email === email && u.password === encodedPassword);

    if (!user) {
        return res.status(401).json({ success: false, error: 'Неверный email или пароль' });
    }

    user.lastLogin = new Date().toLocaleString('ru-RU');
    saveUsers(users);

    res.json({
        success: true,
        message: 'Вход успешен!',
        user: { 
            id: user.id, 
            name: user.name, 
            email: user.email,
            isAdmin: user.isAdmin,
            registeredAt: user.registeredAt
        }
    });
});

// ПОЛУЧИТЬ ПРОФИЛЬ
app.get('/api/user/:id', (req, res) => {
    const userId = parseInt(req.params.id);
    const users = getUsers();
    const user = users.find(u => u.id === userId);

    if (!user) {
        return res.status(404).json({ success: false, error: 'Пользователь не найден' });
    }

    res.json({
        success: true,
        user: {
            id: user.id,
            name: user.name,
            email: user.email,
            registeredAt: user.registeredAt,
            lastLogin: user.lastLogin,
            isAdmin: user.isAdmin
        }
    });
});

// ОБНОВИТЬ ПРОФИЛЬ
app.put('/api/user/:id', (req, res) => {
    const userId = parseInt(req.params.id);
    const { name, email } = req.body;

    if (!name || !email) {
        return res.status(400).json({ success: false, error: 'Имя и email обязательны' });
    }

    const users = getUsers();
    const user = users.find(u => u.id === userId);

    if (!user) {
        return res.status(404).json({ success: false, error: 'Пользователь не найден' });
    }

    // Проверяем, занят ли новый email
    if (email !== user.email && users.some(u => u.email === email)) {
        return res.status(400).json({ success: false, error: 'Этот email уже используется' });
    }

    user.name = name;
    user.email = email;
    saveUsers(users);

    res.json({
        success: true,
        message: 'Профиль обновлен!',
        user: { id: user.id, name: user.name, email: user.email }
    });
});

// ПОЛУЧИТЬ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ (только для админов)
app.get('/api/admin/users', (req, res) => {
    const adminId = req.query.adminId;
    const users = getUsers();
    const admin = users.find(u => u.id === parseInt(adminId));

    if (!admin || !admin.isAdmin) {
        return res.status(403).json({ success: false, error: 'Доступ запрещен' });
    }

    const usersList = users.map(u => ({
        id: u.id,
        name: u.name,
        email: u.email,
        registeredAt: u.registeredAt,
        lastLogin: u.lastLogin,
        isAdmin: u.isAdmin
    }));

    res.json({
        success: true,
        totalUsers: users.length,
        users: usersList
    });
});

// УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ (только для админов)
app.delete('/api/admin/user/:id', (req, res) => {
    const adminId = req.query.adminId;
    const userId = parseInt(req.params.id);

    const users = getUsers();
    const admin = users.find(u => u.id === parseInt(adminId));

    if (!admin || !admin.isAdmin) {
        return res.status(403).json({ success: false, error: 'Доступ запрещен' });
    }

    // Запрещаем удалять самого себя
    if (admin.id === userId) {
        return res.status(400).json({ success: false, error: 'Нельзя удалить самого себя' });
    }

    const initialLength = users.length;
    const updatedUsers = users.filter(u => u.id !== userId);

    if (updatedUsers.length === initialLength) {
        return res.status(404).json({ success: false, error: 'Пользователь не найден' });
    }

    saveUsers(updatedUsers);

    res.json({
        success: true,
        message: 'Пользователь удален'
    });
});

// СТАТИСТИКА
app.get('/api/stats', (req, res) => {
    const users = getUsers();
    
    res.json({
        success: true,
        stats: {
            totalUsers: users.length,
            admins: users.filter(u => u.isAdmin).length,
            registeredToday: users.filter(u => {
                const today = new Date().toLocaleDateString('ru-RU');
                return u.registeredAt.includes(today);
            }).length
        }
    });
});

app.listen(PORT, () => {
    console.log(`
╔════════════════════════════════════════╗
║   InvokerClient Server запущен! 🚀     ║
║   Адрес: http://localhost:${PORT}          ║
║                                        ║
║   👑 АДМИН-ДОСТУП:                    ║
║   📧 Email: gridinamarina999@gmail.com ║
║   🔐 Пароль: q1w2e3334                ║
║                                        ║
║   После входа админа нажми "📊 Панель"║
╚════════════════════════════════════════╝
    `);
});