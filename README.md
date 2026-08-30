# AddressBook

A command-line contact management system built in Python, backed by MySQL, with secure multi-user authentication and per-user contact isolation.

## Features

- **Multi-user accounts** — each user registers their own account and only sees their own contacts
- **Secure authentication** — passwords are hashed with `bcrypt` (never stored in plain text)
- **Session persistence** — stay logged in between runs without re-entering credentials
- **Full contact management** — add, view, search, update, and delete contacts
- **Input validation** — email format and phone number checks before any database write
- **Duplicate protection** — prevents adding or updating a contact into a duplicate name, phone, or email
- **Login history** — every successful login is logged with a timestamp
- **Account deletion** — a user can permanently remove their account and all associated contacts

## Tech Stack

| Component      | Technology              |
|----------------|--------------------------|
| Language       | Python 3                |
| Database       | MySQL                   |
| Password hashing | bcrypt                |
| Config         | python-dotenv (`.env`)  |

## Project Structure

```
AddressBook/
├── Address_Book_6_8_12.py   # Main application
├── schema.sql               # Database schema (run once to set up tables)
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore
└── README.md
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/AddressBook.git
cd AddressBook
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up the database

Make sure MySQL is installed and running, then load the schema:

```bash
mysql -u root -p < schema.sql
```

### 4. Configure environment variables

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

Edit `.env`:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=address_book
```

### 5. Run the app

```bash
python Address_Book_6_8_12.py
```

## Usage

On first run, you'll be prompted to **register** a new account or **log in** to an existing one. Once logged in, the main menu lets you:

```
1. Add contact
2. View contacts
3. Update contact
4. Delete contact
5. Search contact
6. Count contacts
7. Log out
8. Delete account
9. Exit
```

## Database Schema

- **users** — stores username and bcrypt-hashed password
- **Contacts** — stores contact details, linked to the owning user via `User_ID`
- **Login_History** — logs each successful login with a timestamp

See [`schema.sql`](./schema.sql) for full table definitions.

## Versioning

This project follows a `MAJOR.FEATURE.PATCH` convention:

- **MAJOR** — structural/architectural changes
- **FEATURE** — new functionality
- **PATCH** — bug fixes

Current version: **6.8.12**

## Roadmap

- [ ] Export contacts to CSV
- [ ] Password reset flow
- [ ] Contact groups/categories
- [ ] GUI or web interface

## License

This project is open source and available under the [MIT License](LICENSE).

## Author

Built by Barman.
