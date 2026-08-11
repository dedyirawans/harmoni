export const CUSTOMER_TYPES = [
  "Prospect", "New Customer", "Repeat Customer", "VIP", "Corporate",
  "Family", "Group", "Umrah Customer", "Tour Customer", "Agent", "Referral",
];

export const LEAD_SOURCES = [
  "WhatsApp", "Instagram", "Facebook", "TikTok", "Website",
  "Referral", "Event", "Walk-in", "Phone", "N8N", "Other",
];

export const LEAD_STAGES = ["NEW", "CONTACTED", "QUALIFIED", "QUOTATION", "NEGOTIATION", "BOOKING", "PAID", "COMPLETED"];
export const LEAD_LOST = "LOST";

export const STAGE_COLORS = {
  NEW: "bg-slate-100 text-slate-700 border-slate-200",
  CONTACTED: "bg-sky-50 text-sky-700 border-sky-200",
  QUALIFIED: "bg-indigo-50 text-indigo-700 border-indigo-200",
  QUOTATION: "bg-blue-50 text-blue-700 border-blue-200",
  NEGOTIATION: "bg-violet-50 text-violet-700 border-violet-200",
  BOOKING: "bg-amber-50 text-amber-700 border-amber-200",
  PAID: "bg-emerald-50 text-emerald-700 border-emerald-200",
  COMPLETED: "bg-green-50 text-green-700 border-green-200",
  LOST: "bg-red-50 text-red-700 border-red-200",
};

export const FOLLOWUP_ACTIVITIES = ["WhatsApp", "Call", "Email", "Meeting", "Send Quotation", "Payment Reminder", "Other"];
export const GENDERS = ["Male", "Female"];

export const fmtIDR = (n) => "Rp " + Number(n || 0).toLocaleString("id-ID");
export const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—");
export const fmtDateTime = (s) => (s ? new Date(s).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
