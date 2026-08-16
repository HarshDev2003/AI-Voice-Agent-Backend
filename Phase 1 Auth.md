# Phase 1 — Authentication System Implementation Plan

## 1. Objective

Build the authentication system for the AI Personal Voice Assistant using **Supabase Auth + Supabase PostgreSQL**.

### Required features

- Email + password registration
- Email verification using OTP
- Email + password login
- Forgot password
- Password reset
- Session management
- Logout
- Protected FastAPI APIs
- User profile

### Not included

- Phone authentication
- SMS OTP
- Twilio
- WhatsApp authentication
- Custom OTP infrastructure
- Custom JWT generation
- Custom password hashing

---

# 2. Technology Stack

| Component | Technology |
|---|---|
| Backend | FastAPI |
| Database | Supabase PostgreSQL |
| Authentication | Supabase Auth |
| Frontend | React / Next.js |
| Email verification | Supabase Auth |
| Password reset | Supabase Auth |
| JWT | Supabase Auth |
| Database access | Supabase / PostgreSQL |
| Testing | Pytest |

Supabase Auth handles the authentication lifecycle, while Supabase PostgreSQL stores the application's data.

---

# 3. Authentication Architecture

```text
                     Frontend
                         |
                         v
                  Supabase Auth
                         |
             +-----------+-----------+
             |                       |
             v                       v
       Email/Password          Email OTP
          Login               Verification
             |                       |
             +-----------+-----------+
                         |
                         v
                    Supabase Session
                         |
                         v
                    Access Token
                         |
                         v
                     FastAPI
                         |
                         v
                 Protected APIs
                         |
                         v
               Supabase PostgreSQL
```

---

# 4. Registration Flow

A new user registers using email and password.

```text
User
 |
 | Email + Password
 v
Supabase Auth
 |
 | Create account
 v
Verification Email
 |
 | OTP
 v
User enters OTP
 |
 v
Email verified
 |
 v
Authenticated Session
```

### Registration steps

1. User enters email.
2. User enters password.
3. Frontend calls Supabase Auth sign-up.
4. Supabase creates the authentication user.
5. Supabase sends the email verification OTP.
6. User enters the OTP.
7. Frontend verifies the OTP.
8. User becomes authenticated.
9. Application creates/initializes the user's profile.

---

# 5. Login Flow

Login uses **email + password**.

```text
User
 |
 | Email + Password
 v
Supabase Auth
 |
 +---- Email verified? ---- No ----> Ask user to verify email
 |
 Yes
 |
 v
Authenticated Session
 |
 v
Access Token
 |
 v
FastAPI
```

### Important

OTP is **not required for every normal login**.

OTP is used for **email verification during registration**.

If you later want password + OTP as a two-factor authentication flow, that should be implemented as a separate security feature.

---

# 6. Email Verification OTP

Supabase Auth can send an email verification code.

Example:

```text
Your verification code is:

483921
```

### Flow

```text
Sign Up
  |
  v
Supabase Auth
  |
  v
Verification Email
  |
  v
OTP
  |
  v
verifyOtp()
  |
  v
Email Verified
```

Configure the Supabase email template to send the OTP token.

---

# 7. Resend Verification OTP

Provide a resend option.

```text
Didn't receive the code?

[ Resend OTP ]
```

Recommended frontend behavior:

```text
Send OTP
   |
   v
60-second cooldown
   |
   v
Allow resend
```

Supabase Auth provides the email verification flow; do not create a custom OTP table.

---

# 8. Forgot Password

Use Supabase Auth's password-reset functionality.

```text
User
 |
 | Forgot password
 v
Enter Email
 |
 v
Supabase Auth
 |
 v
Password Reset Email
 |
 v
Reset Password Page
 |
 v
New Password
 |
 v
Supabase Auth
 |
 v
Password Updated
```

### API/SDK flow

```text
resetPasswordForEmail()
        |
        v
Password reset email
        |
        v
Recovery session
        |
        v
updateUser({ password })
```

---

# 9. Reset Password

Reset page:

```text
+-----------------------------+
|       Reset Password        |
|                             |
| New Password                |
| +-------------------------+ |
| |                         | |
| +-------------------------+ |
|                             |
| Confirm Password            |
| +-------------------------+ |
| |                         | |
| +-------------------------+ |
|                             |
|     [ Update Password ]     |
+-----------------------------+
```

### Flow

```text
Reset Link
    |
    v
Recovery Session
    |
    v
Enter New Password
    |
    v
Supabase Auth
    |
    v
Password Updated
```

---

# 10. User Profile

Supabase Auth manages authentication data.

Application-specific data should be stored in a separate `profiles` table.

## `profiles`

```text
profiles
--------------------------------
id
email
full_name
avatar_url
preferred_language
timezone
created_at
updated_at
```

`id` should reference the Supabase Auth user ID.

```text
auth.users
    |
    | 1:1
    v
public.profiles
```

Keep the profile table minimal during Phase 1. AI-specific preferences and memory will be added in later phases.

---

# 11. Supabase PostgreSQL

Use Supabase PostgreSQL as the application's main relational database.

Future tables can be added in later phases:

```text
profiles
conversations
messages
reminders
tasks
memories
voice_sessions
call_logs
```

Every application record should be associated with:

```text
user_id
```

which comes from the Supabase Auth user ID.

---

# 12. Row Level Security

Enable RLS on application tables.

For the profile table:

```sql
CREATE POLICY "Users can read their own profile"
ON public.profiles
FOR SELECT
USING (auth.uid() = id);
```

The principle is:

```text
Authenticated User
       |
       v
auth.uid()
       |
       v
RLS Policy
       |
       +---- Own record → Allow
       |
       +---- Other user's record → Deny
```

Do not disable RLS on user-owned application data.

---

# 13. FastAPI Authentication

FastAPI should **validate the Supabase access token** rather than creating its own JWT.

```text
Frontend
   |
   v
Supabase Auth
   |
   v
Supabase Access Token
   |
   v
FastAPI
   |
   v
Validate Token
   |
   v
Get user_id
   |
   v
Protected API
```

Create a reusable dependency:

```text
get_current_user()
```

Use it on protected endpoints.

---

# 14. Protected API Example

```text
GET /api/users/me
```

Request:

```http
Authorization: Bearer <supabase_access_token>
```

Flow:

```text
Request
  |
  v
get_current_user()
  |
  v
Validate Supabase JWT
  |
  v
Extract user_id
  |
  v
Load profile
  |
  v
Return user
```

---

# 15. Required API Endpoints

Authentication actions are handled primarily through Supabase Auth.

FastAPI only needs application-level authentication/user endpoints in this phase.

```text
GET   /api/users/me
PATCH /api/users/me
```

The frontend uses Supabase Auth for:

```text
signUp()
signInWithPassword()
verifyOtp()
resend()
resetPasswordForEmail()
updateUser()
signOut()
```

---

# 16. Backend Structure

Keep the backend simple because Supabase handles most authentication functionality.

```text
backend/
|
├── app/
|   |
|   ├── main.py
|   |
|   ├── core/
|   |   ├── config.py
|   |   ├── database.py
|   |   └── security.py
|   |
|   ├── auth/
|   |   └── dependencies.py
|   |
|   ├── users/
|   |   ├── router.py
|   |   ├── service.py
|   |   └── schemas.py
|   |
|   └── integrations/
|       └── supabase/
|
├── tests/
|   ├── auth/
|   └── users/
|
├── .env
├── .env.example
├── Dockerfile
└── requirements.txt
```

---

# 17. Frontend Structure

```text
frontend/
|
├── src/
|   |
|   ├── pages/
|   |   ├── Login/
|   |   ├── Register/
|   |   ├── VerifyEmail/
|   |   ├── ForgotPassword/
|   |   ├── ResetPassword/
|   |   └── Dashboard/
|   |
|   ├── components/
|   |   ├── LoginForm/
|   |   ├── RegisterForm/
|   |   ├── OTPInput/
|   |   └── ProtectedRoute/
|   |
|   ├── services/
|   |   ├── supabase.js
|   |   └── userApi.js
|   |
|   └── hooks/
|       └── useAuth.js
```

---

# 18. Frontend Screens

## Register

```text
+-----------------------------+
|       Create Account        |
|                             |
| Email                       |
| +-------------------------+ |
| |                         | |
| +-------------------------+ |
|                             |
| Password                    |
| +-------------------------+ |
| |                         | |
| +-------------------------+ |
|                             |
|      [ Create Account ]     |
+-----------------------------+
```

## Verify Email

```text
+-----------------------------+
|      Verify Your Email      |
|                             |
| Enter the 6-digit code      |
| sent to your email.         |
|                             |
| [ 4 ][ 8 ][ 3 ][ 9 ][ 2 ][ 1 ]
|                             |
| [ Verify ]                  |
|                             |
| Resend OTP                  |
+-----------------------------+
```

## Login

```text
+-----------------------------+
|        Welcome Back         |
|                             |
| Email                       |
| +-------------------------+ |
| |                         | |
| +-------------------------+ |
|                             |
| Password                    |
| +-------------------------+ |
| |                         | |
| +-------------------------+ |
|                             |
| [ Login ]                   |
|                             |
| Forgot Password?            |
+-----------------------------+
```

---

# 19. Environment Variables

```env
APP_ENV=development

SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

SUPABASE_DB_URL=

FRONTEND_URL=
```

### Security

Never expose the service-role key to the frontend.

Keep:

```text
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_DB_URL
```

server-side only.

---

# 20. Implementation Milestones

```text
Phase 1 — Authentication
|
├── 1.1 Create Supabase Project
|
├── 1.2 Configure Supabase Auth
|
├── 1.3 Enable Email/Password Authentication
|
├── 1.4 Configure Email Verification OTP
|
├── 1.5 Configure Email Templates
|
├── 1.6 Configure Redirect URLs
|
├── 1.7 Create profiles Table
|
├── 1.8 Configure RLS
|
├── 1.9 Create FastAPI Project
|
├── 1.10 Connect FastAPI to Supabase
|
├── 1.11 Implement JWT Validation
|
├── 1.12 Implement get_current_user()
|
├── 1.13 Implement User Profile API
|
├── 1.14 Build Register UI
|
├── 1.15 Build Email OTP Verification UI
|
├── 1.16 Build Login UI
|
├── 1.17 Build Forgot Password UI
|
├── 1.18 Build Reset Password UI
|
├── 1.19 Add Authentication Tests
|
└── 1.20 Security Review
```

---

# 21. Implementation Order

```text
1. Create Supabase project
        |
        v
2. Enable Email/Password Auth
        |
        v
3. Configure email verification
        |
        v
4. Configure OTP email template
        |
        v
5. Configure redirect URLs
        |
        v
6. Test signup + email OTP
        |
        v
7. Create profiles table
        |
        v
8. Configure RLS
        |
        v
9. Create FastAPI project
        |
        v
10. Configure Supabase connection
        |
        v
11. Implement JWT validation
        |
        v
12. Implement get_current_user()
        |
        v
13. Implement /api/users/me
        |
        v
14. Build registration UI
        |
        v
15. Build OTP verification UI
        |
        v
16. Build email/password login
        |
        v
17. Build forgot-password flow
        |
        v
18. Build reset-password flow
        |
        v
19. Test authentication
        |
        v
20. Phase 1 complete
```

---

# 22. Testing Checklist

## Registration

- [ ] Valid email and password
- [ ] Invalid email
- [ ] Weak password
- [ ] Duplicate email
- [ ] Verification email received
- [ ] Valid OTP
- [ ] Invalid OTP
- [ ] Expired OTP
- [ ] Resend verification OTP
- [ ] Unverified user cannot access protected features

## Login

- [ ] Correct email/password
- [ ] Incorrect password
- [ ] Non-existent email
- [ ] Unverified email
- [ ] Successful login creates session
- [ ] Access token works

## Forgot Password

- [ ] Valid email
- [ ] Reset email received
- [ ] Valid reset link
- [ ] Expired/invalid reset link
- [ ] New password accepted
- [ ] Old password no longer works

## Authorization

- [ ] Protected API rejects unauthenticated request
- [ ] Valid Supabase token is accepted
- [ ] Invalid token is rejected
- [ ] Expired token is rejected
- [ ] User can access only their own profile
- [ ] RLS prevents cross-user data access

---

# 23. Definition of Done

Phase 1 is complete when:

- [ ] User can register with email + password
- [ ] Verification email is sent
- [ ] User can verify email using OTP
- [ ] User can resend verification OTP
- [ ] Verified user can log in with email + password
- [ ] Unverified user cannot access protected application features
- [ ] Forgot password works
- [ ] Reset password works
- [ ] Supabase session works
- [ ] FastAPI validates Supabase access tokens
- [ ] `/api/users/me` works
- [ ] `profiles` table exists
- [ ] RLS policies are implemented
- [ ] Users cannot access another user's data
- [ ] Register UI works
- [ ] OTP verification UI works
- [ ] Login UI works
- [ ] Forgot/reset password UI works
- [ ] Authentication tests pass
- [ ] Security tests pass
- [ ] Secrets are not committed to Git

---

# 24. Final Architecture

```text
                         PHASE 1 AUTH
                              |
                              v
                         Supabase Auth
                              |
                +-------------+-------------+
                |                           |
                v                           v
         Email + Password              Email OTP
             Login                  Verification
                |                           |
                +-------------+-------------+
                              |
                              v
                       Supabase Session
                              |
                              v
                        Access Token
                              |
                              v
                           FastAPI
                              |
                       JWT Validation
                              |
                              v
                       Protected APIs
                              |
                              v
                    Supabase PostgreSQL
                              |
                              v
                         profiles
```

## Phase 1 Principle

Keep authentication simple:

**Supabase Auth = authentication**

**Supabase PostgreSQL = application database**

**FastAPI = backend/business logic**

**Frontend = authentication UI**

Do not rebuild authentication infrastructure that Supabase already provides.

---

# 25. Next Phase

After Phase 1 is complete, proceed to:

**Phase 2 — Conversation Management**

The authenticated Supabase `user_id` will be used to associate:

```text
User
 |
 +-- Conversations
 |      |
 |      +-- Messages
 |
 +-- Preferences
 +-- Memories
 +-- Reminders
 +-- Tasks
 +-- Voice Sessions
 +-- Phone Calls
```
