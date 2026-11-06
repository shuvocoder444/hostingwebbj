# 🚀 Hostinger-Style Unified hPanel Master Architecture & Implementation Plan
## (Shared Hosting + VPS Cloud Management Suite for VeloHoster)

> **ভিশন ও লক্ষ্য:** 
> ক্লায়েন্টদের জন্য Hostinger-এর হুবহু **hPanel** ইন্টারফেস তৈরি করা, যেখানে একই প্ল্যাটফর্মে **Shared Hosting** (cPanel/WHM ব্যাকএন্ড) এবং **Cloud VPS Hosting** (KVM/Virtualizor/Proxmox/Cloud API) সম্পূর্ণ নিজস্ব ব্র্যান্ডিংয়ে ১-ক্লিকে পরিচালিত হবে।

---

## 📸 রেফারেন্স ডিজাইন বিশ্লেষণ (Hostinger Official UI Structure)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [H] VELOHOSTER   Home   Hosting   Domains   Emails   Servers (VPS)   Billing   🔔 👤 │
├───────────────────────────────┬────────────────────────────────────────────────────────┤
│ 🌐 [ your-domain.com    ▼ ]   │ 🧭 Breadcrumbs: Hosting > your-domain.com > Website    │
│                               ├────────────────────────────────────────────────────────┤
│ 📊 Dashboard                  │ 📈 Live Analytics & Resource Usage                     │
│ 🚀 WordPress / Website     >  │    [ 995.09 MB Bandwidth ]    [ 20,040 Requests ]      │
│    ├─ Auto Installer (1-Click)│                                                        │
│    ├─ WP Admin Auto-Login     │ 📊 Top Visitors by Country, IP, Error 5xx & 4xx Logs   │
│    └─ Access & Error Logs     ├────────────────────────────────────────────────────────┤
│ 📁 Files & Backups         >  │ ⚡ Quick Actions: [File Manager] [phpMyAdmin] [Webmail]│
│ 🗄️ Databases               >  ├────────────────────────────────────────────────────────┤
│ ✉️ Emails                  >  │ ⚙️ Module Workplace (Tab Content / Tool View)         │
│ 🌐 Domains & SSL           >  │                                                        │
│ ⚙️ Advanced (PHP/Cron/DNS) >  │                                                        │
└───────────────────────────────┴────────────────────────────────────────────────────────┘
```

---

## 🏗️ ১. ডুয়াল আর্কিটেকচার (Dual Hosting Engine Architecture)

আমাদের সিস্টেম ব্যাকএন্ডে দুটি পৃথক ইঞ্জিন সমর্থন করবে, কিন্তু ক্লায়েন্টের জন্য থাকবে একটাই প্রিমিয়াম hPanel:

```
                               ┌─────────────────────────────┐
                               │     VeloHoster Frontend     │
                               │  (Hostinger hPanel Clone)   │
                               └──────────────┬──────────────┘
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 ▼
        ┌─────────────────────────┐                       ┌─────────────────────────┐
        │  Shared Hosting Engine  │                       │    Cloud VPS Engine     │
        │      (cPanel / WHM)     │                       │  (Virtualizor/Proxmox)  │
        ├─────────────────────────┤                       ├─────────────────────────┤
        │ • 1-Click WordPress     │                       │ • Power (Reboot/Boot)   │
        │ • File Manager SSO      │                       │ • 1-Click OS Reinstall  │
        │ • MySQL & phpMyAdmin    │                       │   (Ubuntu, aaPanel, WHM)│
        │ • Business Emails       │                       │ • Web VNC Terminal      │
        │ • AutoSSL & DNS Records │                       │ • CPU/RAM Live Graphs   │
        └─────────────────────────┘                       └─────────────────────────┘
```

---

## 📋 ২. স্টেপ-বাই-স্টেপ মাস্টার রোডম্যাপ (8-Phase Implementation Plan)

### 🔹 ফেজ ১: মাস্টার লেআউট ও সাইডবার নেভিগেশন (Hostinger Exact Sidebar Clone)
- [x] টপ নেভিগেশন বার (`Home`, `Hosting`, `Domains`, `Emails`, `Servers`, `Billing`)
- [ ] বামপাশের মাল্টি-লেভেল কোলাপসিবল নেভিগেশন সাইডবার (ডোমেন ড্রপডাউন সিলেক্টরসহ)
- [ ] ব্রেডক্রাম্ব নেভিগেশন ও রেসপনসিভ মোবাইল সাইডবার টগল

---

### 🔹 ফেজ ২: Shared Hosting — 1-Click WordPress & Website Suite
- [ ] **1-Click Auto Installer:** সাইট টাইটেল, অ্যাডমিন ইউজারনেম, পাসওয়ার্ড ও ইমেইল ইনপুট দিয়ে সফটঅ্যাকুলাস/WP-CLI দিয়ে সরাসরি ওয়ার্ডপ্রেস ইন্সটল।
- [ ] **WP Admin Auto-Login:** কোনো পাসওয়ার্ড ছাড়া ক্লায়েন্ট সরাসরি ড্যাশবোর্ড থেকে `/wp-admin`-এ ১-ক্লিকে লগইন করতে পারবে।
- [ ] **WordPress Toolkit:** ওয়ার্ডপ্রেস কোর ভার্সন, প্লাগইন ও থিম স্ট্যাটাস, মেইনটেন্যান্স মোড টগল।
- [ ] **Access & Error Logs Viewer:** লাস্ট এরর কোড (5xx, 4xx) অ্যানালিটিক্স এবং ভিজিটর কান্ট্রি ট্রাফিক ভিউ (Hostinger স্ক্রিনশট অনুযায়ী)।

---

### 🔹 ফেজ ৩: Shared Hosting — Files & Backups Suite
- [x] Hostinger স্টাইল ৪-কার্ড ফাইল ওভারভিউ (File Manager, Backups, FTP Accounts, Password Change)
- [x] File Manager 1-Click SSO ডিরেক্টরি ওপেনার
- [ ] ব্রাউজারের ভেতর ফাইল জিপ/আনজিপ ও এডিট করার ইন-প্যানেল ইন্টারফেস
- [ ] ব্যাকআপ জেনারেটর ও ১-ক্লিক ব্যাকআপ ডাউনলোড সিস্টেম
- [ ] FTP অ্যাকাউন্ট তৈরি ও ডিরেক্টরি পাথ পারমিশন সেটআপ

---

### 🔹 ফেজ ৪: Shared Hosting — Databases & phpMyAdmin Suite
- [x] MySQL ডাটাবেস ও ইউজার তৈরির ইন-অ্যাপ ফর্ম
- [x] phpMyAdmin ১-ক্লিক অটো-লগইন (SSO)
- [x] ডাটাবেস লিস্ট, সাইজ এবং টেবিল কাউন্ট
- [ ] রিমোট MySQL অ্যাক্সেস কন্ট্রোল (IP হোয়াইটলিস্টিং)

---

### 🔹 ফেজ ৫: Shared Hosting — Business Email Suite
- [x] নতুন ইমেইল অ্যাকাউন্ট তৈরি (`info@yourdomain.com`)
- [x] ওয়েবমেইল (Roundcube) ১-ক্লিক পাসওয়ার্ডবিহীন লগইন
- [x] ইমেইল কোটা লিমিট ও পাসওয়ার্ড পরিবর্তন
- [ ] ইমেইল ফরওয়ার্ডার (Forwarders) ও অটোরেসপন্ডার (Autoresponders) ম্যানেজমেন্ট
- [ ] SPF, DKIM ও MX রেকর্ড ভ্যালিডেশন চেকার

---

### 🔹 ফেজ ৬: Shared Hosting — Domains, DNS & Advanced
- [x] সাবডোমেন তৈরি ও লাইভ ডোমেন লিস্ট
- [x] Free AutoSSL স্ট্যাটাস এবং ১-ক্লিক SSL ইস্যু
- [ ] DNS Zone Editor (A Record, CNAME, MX, TXT রেকর্ড লাইভ এডিটিং)
- [ ] PHP Version Selector (PHP 7.4, 8.0, 8.1, 8.2, 8.3 এক ক্লিকে পরিবর্তন)
- [ ] Cron Jobs শিডিউলার (WooCommerce, Laravel বা কাস্টম ক্রন সেটআপ)

---

### 🔹 ফেজ ৭: Cloud VPS Management Suite (Ubuntu, aaPanel, WHM Reinstaller)
- [ ] **VPS ডেটাবেস মডেল:** `VPSInstance` (Server IP, OS, RAM, vCPU, Status, Root User)
- [ ] **VPS Power Controls:**
  - 🟢 **Start / Boot**
  - 🔄 **Reboot / Restart**
  - 🔴 **Power Off / Force Shutdown**
- [ ] **1-Click OS & Panel Reinstaller Modal (ঠিক Hostinger-এর মতো):**
  - 🐧 *Plain OS:* Ubuntu 24.04, Ubuntu 22.04, Debian 12, AlmaLinux 9
  - 🚀 *With Control Panels:*
    - **Ubuntu + aaPanel** (রেডিমেড পোর্ট 8888 সহ)
    - **AlmaLinux + cPanel / WHM**
    - **Ubuntu + CyberPanel** (OpenLiteSpeed)
    - **Ubuntu + Docker & Portainer**
  - রুট পাসওয়ার্ড সেট করে ইনস্টল বাটনে চাপ দিলে ব্যাকএন্ডে ২ মিনিটে নতুন ওএস সেট হবে।
- [ ] **Emergency Web Console (noVNC / Web Terminal):** ব্রাউজারের ভেতর ব্ল্যাক স্ক্রিন SSH টার্মিনাল।
- [ ] **Live VPS Graphs:** লাইভ CPU %, RAM %, Disk I/O এবং ব্যান্ডউইথ ব্যবহারের চার্ট।
- [ ] **Root Password Reset:** ১-ক্লিকে নতুন রুট পাসওয়ার্ড জেনারেট।

---

### 🔹 ফেজ ৮: হোয়াইটলেবেল মোড ও সিকিউরিটি পলিশ
- [ ] যে অ্যাকাউন্টগুলোতে আপনি cPanel অ্যাক্সেস দিতে চান না, সেগুলোতে cPanel বাটন সম্পূর্ণ লুকিয়ে ফেলা হবে।
- [ ] রিয়েল-টাইম কাস্টমার নোটিফিকেশন ও অ্যালার্ট সিস্টেম।
- [ ] লাইভ টেস্ট ও প্রোডাকশন ডেপ্লয়মেন্ট ভেরিফিকেশন।

---

## 🎯 পরবর্তী অ্যাকশন
আমরা এখনই **ফেজ ১ (Hostinger-এর মতো কমপ্লিট মাল্টি-লেভেল সাইডবার লেআউট)** এবং **ফেজ ২ (1-Click WordPress & Website Suite)** দিয়ে কাজ শুরু করতে পারি।

