import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import Home from "./pages/Home.jsx";
import RepoDetail from "./pages/RepoDetail.jsx";
import JobPage from "./pages/JobPage.jsx";
import repoRadarLogo from "./assets/reporadar-logo-v3.svg";
import "./index.css";

function BrandBar() {
  const { pathname } = useLocation();
  const showHomeLink = pathname.startsWith("/repo/") || pathname.startsWith("/job/");

  return (
    <div className="brand-row">
      <Link to="/" className="brand">
        <img
          src={repoRadarLogo}
          alt="RepoRadar"
          className="brand-logo"
        />
      </Link>
      {showHomeLink && (
        <Link to="/" className="btn btn-ghost home-link">
          Home
        </Link>
      )}
    </div>
  );
}

function Footer() {
  return (
    <footer className="site-footer">
      <strong>RepoRadar</strong> — AI-powered GitHub repository architect.
      Paste a repo URL, get its architecture, smells, and onboarding guide.
    </footer>
  );
}

function NotFound() {
  return (
    <div className="not-found">
      <h1>404</h1>
      <p>The page you are looking for does not exist.</p>
      <Link to="/" className="btn btn-primary">
        Back to Home
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <BrandBar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/repo/:id" element={<RepoDetail />} />
            <Route path="/job/:jobId" element={<JobPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  );
}
