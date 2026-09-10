import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL || "";

const portalApi = axios.create({ baseURL: `${BASE}/api` });

portalApi.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("portal_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export default portalApi;
