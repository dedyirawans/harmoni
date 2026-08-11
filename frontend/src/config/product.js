export const PRODUCT_TYPES = [
  { value: "UMROH", label: "Umroh" },
  { value: "TOUR", label: "Paket Tour" },
  { value: "UMROH_PLUS", label: "Umroh Plus" },
];

export const TYPE_LABEL = { UMROH: "Umroh", TOUR: "Paket Tour", UMROH_PLUS: "Umroh Plus" };

export const SUB_BY_TYPE = {
  UMROH: [
    { value: "PRIVATE", label: "Umroh Private" },
    { value: "OPEN_TRIP", label: "Umroh Open Trip" },
    { value: "SEAT_IN_COACH", label: "Umroh Seat in Coach" },
  ],
  TOUR: [
    { value: "PRIVATE", label: "Private Tour" },
    { value: "OPEN_TRIP", label: "Tour Open Trip" },
    { value: "SEAT_IN_COACH", label: "Tour Seat in Coach" },
  ],
  UMROH_PLUS: [
    { value: "PRIVATE", label: "Private" },
    { value: "OPEN_TRIP", label: "Open Trip" },
    { value: "SEAT_IN_COACH", label: "Seat in Coach" },
  ],
};

export const subLabel = (type, sub) => {
  const arr = SUB_BY_TYPE[type] || [];
  return (arr.find((s) => s.value === sub) || {}).label || sub || "";
};

export const PACKAGE_STATUSES = ["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"];
export const ROOM_TYPES = ["QUAD", "TRIPLE", "DOUBLE", "SUITE"];

export const PKG_STATUS_COLORS = {
  DRAFT: "bg-slate-100 text-slate-600 border-slate-200",
  ACTIVE: "bg-emerald-50 text-emerald-700 border-emerald-200",
  INACTIVE: "bg-amber-50 text-amber-700 border-amber-200",
  ARCHIVED: "bg-red-50 text-red-700 border-red-200",
};

export const DEP_STATUS_COLORS = {
  OPEN: "bg-emerald-50 text-emerald-700 border-emerald-200",
  "ALMOST FULL": "bg-amber-50 text-amber-700 border-amber-200",
  FULL: "bg-red-50 text-red-700 border-red-200",
  CLOSED: "bg-slate-100 text-slate-600 border-slate-200",
  CANCELLED: "bg-red-50 text-red-700 border-red-200",
};

export const UMRAH_FIELDS = [
  ["makkah_hotel", "Makkah Hotel"], ["madinah_hotel", "Madinah Hotel"],
  ["makkah_nights", "Makkah Nights"], ["madinah_nights", "Madinah Nights"],
  ["airline", "Airline"], ["visa", "Visa"], ["transport", "Transport"],
  ["handling", "Handling"], ["muthawwif", "Muthawwif"], ["manasik", "Manasik"],
  ["zamzam", "Zam Zam"], ["insurance", "Insurance"], ["baggage", "Baggage"], ["room_type", "Room Type"],
];

export const COST_COMPONENTS = [
  ["flight", "Flight"], ["hotel", "Hotel"], ["visa", "Visa"], ["transport", "Transport"],
  ["guide", "Guide"], ["muthawwif", "Muthawwif"], ["handling", "Handling"],
  ["meal", "Meal"], ["insurance", "Insurance"], ["other", "Other Cost"],
];
