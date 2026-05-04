import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquarePlus,
  Settings,
  LogOut,
  Menu,
  X,
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { useIsMobile } from '../../hooks/use-mobile';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/quote/new', label: 'Neues Angebot', icon: MessageSquarePlus },
  { to: '/settings', label: 'Einstellungen', icon: Settings },
];

const navLinkClass = ({ isActive }) =>
  [
    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
    isActive
      ? 'bg-blue-600 text-white'
      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900',
  ].join(' ');

const SidebarContent = ({ user, onLogout, onItemClick }) => (
  <div className="flex h-full flex-col">
    <div className="px-4 py-5 border-b border-gray-200">
      <p className="text-base font-semibold text-gray-900">Maler KV</p>
      <p className="text-xs text-gray-500">Kostenvoranschläge per Chat</p>
    </div>

    <nav className="flex-1 px-3 py-4 space-y-1">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/dashboard'}
          className={navLinkClass}
          onClick={onItemClick}
        >
          <item.icon className="h-4 w-4" />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>

    <div className="border-t border-gray-200 px-3 py-4 space-y-2">
      <div className="px-3 text-xs text-gray-500">
        Angemeldet als
      </div>
      <div className="px-3 text-sm font-medium text-gray-800 truncate">
        {user?.company_name || user?.username || user?.email || '—'}
      </div>
      <button
        type="button"
        onClick={onLogout}
        className="w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-gray-700 hover:bg-red-50 hover:text-red-700 transition-colors"
      >
        <LogOut className="h-4 w-4" />
        Abmelden
      </button>
    </div>
  </div>
);

const AppLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile drawer on viewport change away from mobile
  useEffect(() => {
    if (!isMobile) setMobileOpen(false);
  }, [isMobile]);

  const handleLogout = async () => {
    setMobileOpen(false);
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Desktop sidebar */}
      {!isMobile && (
        <aside className="w-60 shrink-0 border-r border-gray-200 bg-white sticky top-0 h-screen">
          <SidebarContent user={user} onLogout={handleLogout} />
        </aside>
      )}

      {/* Mobile drawer */}
      {isMobile && mobileOpen && (
        <div className="fixed inset-0 z-40 flex">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative z-50 w-72 bg-white shadow-xl">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="absolute top-3 right-3 rounded-md p-1 text-gray-500 hover:bg-gray-100"
              aria-label="Menü schließen"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent
              user={user}
              onLogout={handleLogout}
              onItemClick={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top-bar with hamburger */}
        {isMobile && (
          <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-gray-200 bg-white px-4 py-3 shadow-sm">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-md p-1 text-gray-700 hover:bg-gray-100"
              aria-label="Menü öffnen"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="text-sm font-semibold text-gray-900">
              Maler KV
            </span>
          </header>
        )}

        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
};

export default AppLayout;
