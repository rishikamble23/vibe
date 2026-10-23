import { Routes, Route, Navigate } from 'react-router-dom';
import { ControlRoom } from './control/ControlRoom';
import { RiderPWA } from './rider/RiderPWA';
import { ShelterTablet } from './shelter/ShelterTablet';
import { DonorForm } from './donor/DonorForm';
import './App.css';

function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<Navigate to="/control" replace />} />
        <Route path="/control" element={<ControlRoom />} />
        <Route path="/rider" element={<RiderPWA />} />
        <Route path="/shelter" element={<ShelterTablet />} />
        <Route path="/donor" element={<DonorForm />} />
      </Routes>
    </div>
  );
}

export default App;