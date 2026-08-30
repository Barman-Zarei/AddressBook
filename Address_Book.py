try:
    # moudels
    import mysql.connector
    import os
    import bcrypt
    from dotenv import load_dotenv
    import random
    import re

    # database connection

    load_dotenv()
    
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    cursor = conn.cursor(dictionary=True)

    current_user_id = None

    # functions
    def register_user():
        print("Create new acount")
        global user_name
        user_name = input("Write a user name: ").strip()
        global password
        password = input("Write a password: ").strip()

        cursor.execute("SELECT * FROM users WHERE Name=%s", (user_name,))
        if cursor.fetchone():
            print("User already exists")
            print("-" * random.randint(26, 30))
            return None

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO users (Name, Password) VALUES (%s, %s)",
            (user_name, hashed_password.decode('utf-8'))
        )
        conn.commit()
        print(f"Acount created for {user_name}")
        print("-" * random.randint(26, 30))

        cursor.execute("SELECT ID FROM users WHERE Name=%s", (user_name,))
        return cursor.fetchone()["ID"]

    def login_user():
        print("Login:")
        user_name = input("Write a user name: ").strip()
        password = input("Write a password: ").strip()

        cursor.execute("SELECT * FROM users WHERE Name=%s", (user_name,))
        user = cursor.fetchone()

        if not user:
            print("User not found")
            print("-" * random.randint(26, 30))
            return None

        if bcrypt.checkpw(password.encode('utf-8'), user["Password"].encode('utf-8')):
            print(f"Welcome back {user_name}")
            save_session(user["ID"])
            print("-" * random.randint(26, 30))
            cursor.execute(
                "INSERT INTO Login_History (User_ID) VALUES (%s)",
                (user["ID"],)
            )
            conn.commit()
            return user["ID"]
        else:
            print("Incorrect password")
            print("-" * random.randint(26, 30))
            return None

    def save_session(user_id):
        with open("user.txt", "w") as f:
            f.write(str(user_id))

    def load_session():
        try:
            with open("user.txt", "r") as f:
                return str(f.read().strip())
        except FileNotFoundError:
            return None
    def logout():
        with open("user.txt", "w") as f:
            f.write("")
        login_register()
    def login_register():
        global current_user_id
        current_user_id = load_session()

        while current_user_id is None or current_user_id == "":
            print("1. Login")
            print("2. Register")
            choice = int(input("Enter your choice (1/2): ").strip())

            if choice == 1:
                    current_user_id = login_user()
            elif choice == 2:
                    current_user_id = register_user()
            else:
                print("Invaild choice")
                print("-" * random.randint(26, 30))

    def add_contact():
        print("Add new contact:")
        name = input("Name: ").strip()
        phone = input("Phone: ").strip()
        Email = input("Email: ").strip()
        address = input("Address: ").strip()
        city = input("City: ").strip()
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, Email):
            print("Invaild Email format")
            print("-" * random.randint(26, 30))
            return
        if not phone.isdigit():
            print("Phone must be number")
            print("-" * random.randint(26, 30))
            return

        cursor.execute(
            "SELECT * FROM Contacts WHERE User_ID=%s AND (LOWER(Email)=%s OR LOWER(Name)=%s OR Phone=%s)",
            (current_user_id, Email.lower(), name.lower(), phone)
        )
        if cursor.fetchone():
            print("The contact already exists")
            print("-" * random.randint(26, 30))
            return

        cursor.execute(
            "INSERT INTO Contacts (Name, Phone, Email, Address, City, User_ID) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, phone, Email, address, city, current_user_id)
        )
        conn.commit()
        print(f"{name} has been added to Address Book")
        print("-" * random.randint(26, 30))

    def view_contact():
        print("-" * random.randint(26, 30))
        print('Your Address Book:')
        cursor.execute("SELECT * FROM Contacts WHERE User_ID=%s ORDER BY Name", (current_user_id,))
        for contact in cursor.fetchall():
            print(f"Name: {contact['Name']}")
            print(f"Phone: {contact['Phone']}")
            print(f"Email: {contact['Email']}")
            print(f"Address: {contact['Address']}")
            print(f"City: {contact['City']}")
            print("-" * random.randint(26, 30))
    
    def delete_acount():
        yon = input("Are you sure (yes/no): ")
        if yon == "yes":
            with open("user.txt", "w") as f:
                f.write("")
            cursor.execute("DELETE FROM login_history WHERE User_ID=%s", (current_user_id,))
            cursor.execute("DELETE FROM contacts WHERE User_ID=%s", (current_user_id,))
            cursor.execute("DELETE FROM users WHERE ID=%s", (current_user_id,))
            conn.commit()
            print("Acount deleted")
            print("-" * random.randint(29, 30))
            login_register()
        elif yon == "no":
            print("Delete canceled")
            print("-" * random.randint(26, 30))
            return

    def update_contact():
        print("Update a contact")
        phone = input("Enter a phone number or name of a contact to update: ").strip()
        cursor.execute("SELECT * FROM Contacts WHERE User_ID=%s AND (Phone=%s OR Name=%s)", (current_user_id, phone, phone))
        contact = cursor.fetchone()

        if contact:
            print("-" * random.randint(26, 30))
            print(f"Current Details for {contact['Name']}")
            print(f"Name: {contact['Name']}")
            print(f"Phone: {contact['Phone']}")
            print(f"Email: {contact['Email']}")
            print(f"Address: {contact['Address']}")
            print(f"City: {contact['City']}")
            print("-" * random.randint(26, 30))

            new_name = input("New Name (Press enter to keep current): ").strip()
            new_Phone = input("New Phone (Press enter to keep current): ").strip()
            new_email = input("New Email (Press enter to keep current): ").strip()
            new_address = input("New Address (Press enter to keep current): ").strip()
            new_city = input("New City (Press enter to keep current): ").strip()

            # Validate email BEFORE changing anything, so we never end up half-updated
            if new_email:
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, new_email):
                    print("Invaild Email format. Update cancelled")
                    print("-" * random.randint(26, 30))
                    return

            # Validate phone BEFORE changing anything
            if new_Phone and not new_Phone.isdigit():
                print("Phone must be number. Update cancelled")
                print("-" * random.randint(26, 30))
                return

            # Check duplicates against OTHER contacts (not this one)
            cursor.execute(
                "SELECT * FROM Contacts WHERE User_ID=%s AND Contact_ID != %s AND "
                "(LOWER(Name)=%s OR Phone=%s OR LOWER(Email)=%s)",
                (
                    current_user_id,
                    contact["Contact_ID"],
                    new_name.lower() if new_name else "",
                    new_Phone if new_Phone else "",
                    new_email.lower() if new_email else ""
                )
            )
            if cursor.fetchone():
                print("Another contact already has this name, phone or email")
                print("-" * random.randint(26, 30))
                return

            # Build the update using whatever the user actually changed
            name_final = new_name if new_name else contact["Name"]
            phone_final = new_Phone if new_Phone else contact["Phone"]
            email_final = new_email if new_email else contact["Email"]
            address_final = new_address if new_address else contact["Address"]
            city_final = new_city if new_city else contact["City"]

            cursor.execute(
                "UPDATE Contacts SET Name=%s, Phone=%s, Email=%s, Address=%s, City=%s WHERE Contact_ID=%s",
                (name_final, phone_final, email_final, address_final, city_final, contact["Contact_ID"])
            )
            conn.commit()
            print(f"Contact detail {name_final} has been updated")
            print("-" * random.randint(26, 30))
            return

        print("Contact not found")
        print("-" * random.randint(26, 30))

    def delete_contact():
        print("-" * random.randint(26, 30))
        print("delete a contact")
        phone = input("Enter a phone number or name of a contact to delete: ").strip()
        cursor.execute("SELECT * FROM Contacts WHERE User_ID=%s AND (Phone=%s OR Name=%s)", (current_user_id, phone, phone))
        contact = cursor.fetchone()

        if contact:
            print("-" * random.randint(26, 30))
            print(f"Current Details for {contact['Name']}")
            print(f"Name: {contact['Name']}")
            print(f"Phone: {contact['Phone']}")
            print(f"Email: {contact['Email']}")
            print(f"Address: {contact['Address']}")
            print(f"City: {contact['City']}")
            deleted_name = contact["Name"]
            yon = input("Are you sure (yes/no): ").strip().lower()
            if yon == "yes":
                cursor.execute("DELETE FROM Contacts WHERE Contact_ID=%s", (contact["Contact_ID"],))
                conn.commit()
                print(f"{deleted_name} has been deleted")
            else:
                print("Delete cancelled")
            print("-" * random.randint(26, 30))
            return

        print("Contact not found")
        print("-" * random.randint(26, 30))

    def search_contact():
        try:
            print("-" * random.randint(26, 30))
            print("Search a contact")
            name_or_phone = input("Enter a phone number or name of a contact to search: ").strip()
            cursor.execute(
                "SELECT * FROM Contacts WHERE User_ID=%s AND (Phone LIKE %s OR LOWER(Name) LIKE %s)",
                (current_user_id, f"%{name_or_phone}%", f"%{name_or_phone.lower()}%")
            )
            matches = cursor.fetchall()
            if not matches:
                print("Contact not found")
                print("-" * random.randint(26, 30))
                return

            for i, contact in enumerate(matches, start=1):
                print(f"{i}. {contact['Name']}")
            choice = int(input("Enter the number of contact you want: "))
            contact = matches[choice - 1]
            print(f"Current Details for {contact['Name']}")
            print(f"Name: {contact['Name']}")
            print(f"Phone: {contact['Phone']}")
            print(f"Email: {contact['Email']}")
            print(f"Address: {contact['Address']}")
            print(f"City: {contact['City']}")
            print("-" * random.randint(26, 30))
        except (ValueError, IndexError):
            print("Invaild selection")
            print("-" * random.randint(26, 30))

    def count_count():
        print("-" * random.randint(26, 30))
        cursor.execute("SELECT COUNT(*) as total FROM Contacts WHERE User_ID=%s", (current_user_id,))
        total = cursor.fetchone()["total"]
        print(f"Total contacts: {total}")
        print("-" * random.randint(26, 30))
    # Login/Register
    login_register()

    # loop
    while True:
        print("Address Book Menu:")
        print("1. Add contact")
        print("2. View contacts")
        print("3. Update contact")
        print("4. Delete contact")
        print("5. Search contact")
        print("6. Count contacts")
        print("7. log out")
        print("8. Delete acount")
        print("9. Exit")
        choice = int(input("Enter your choice (1/2/3/4/5/6/7/8/9): ").strip())
        if choice == 1:
            add_contact()
        elif choice == 2:
            view_contact()
        elif choice == 3:
            update_contact()
        elif choice == 4:
            delete_contact()
        elif choice == 5:
            search_contact()
        elif choice == 6:
            count_count()
        elif choice == 7:
            logout()
        elif choice == 8:
            delete_acount()
        elif choice == 9:
            print("Good bye")
            cursor.close()
            conn.close()
            break
        else:
            print("Invaild choice")
except Exception as e:
    print("Error:", e)
