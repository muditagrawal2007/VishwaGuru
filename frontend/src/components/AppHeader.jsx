import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { Menu, User, LogOut } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const AppHeader = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, logout } = useAuth(); // useAuth returns user, not currentUser
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Failed to log out', error);
    }
  };

  return (
    <header className="bg-white shadow-sm sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center cursor-pointer" onClick={() => navigate('/')}>
            <span className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-orange-500 via-orange-400 to-green-500 drop-shadow-sm">
              VishwaGuru
            </span>
          </div>

          <div className="flex items-center gap-4">
             {user ? (
                <div className="relative">
                  <button onClick={() => setIsMenuOpen(!isMenuOpen)} className="flex items-center gap-2 text-gray-700 hover:text-blue-600 focus:outline-none">
                    <div className="bg-blue-100 p-2 rounded-full">
                        <User size={20} className="text-blue-600" />
                    </div>
                    <span className="hidden sm:inline font-medium text-sm">{user.email}</span>
                  </button>

                  {isMenuOpen && (
                    <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 ring-1 ring-black ring-opacity-5 z-50">
                      <Link to="/my-reports" className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100" onClick={() => setIsMenuOpen(false)}>My Reports</Link>
                      <button onClick={handleLogout} className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2">
                        <LogOut size={14} /> Logout
                      </button>
                    </div>
                  )}
                </div>
             ) : (
                <Link to="/login" className="text-sm font-medium text-blue-600 hover:text-blue-500 px-4 py-2 rounded-full hover:bg-blue-50 transition-colors">Login</Link>
             )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default AppHeader;
