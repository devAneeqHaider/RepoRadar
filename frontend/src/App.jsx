import { BrowserRouter, Routes, Route, Link, NavLink } from "react-router-dom";
import Home from "./pages/Home.jsx";
import RepoDetail from "./pages/RepoDetail.jsx";
import JobPage from "./pages/JobPage.jsx";
import "./index.css";

function Header() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            ◎
          </span>
          RepoRadar
        </Link>
        <nav className="nav-links">
          <NavLink
            to="/"
            end
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            Home
          </NavLink>
        </nav>
      </div>
    </header>
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
        <Header />
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
