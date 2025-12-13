function sys = get_system_config()
% GET_SYSTEM_CONFIG
% Defines all constants for the Overwatch Simulation.
% EDIT THIS FILE to match your Thesis Parameters.

    %% 1. SYSTEM BASICS
    sys.V_LL = 13200;       % Nominal Line-to-Line Voltage (13.2 kV)
    sys.S_base = 5e6;       % Base MVA (5 MVA)
    sys.F_Hz = 60;          % Frequency (60 Hz)
    
    % Derived Base Values
    sys.V_LN = sys.V_LL / sqrt(3);           % Line-to-Neutral Voltage
    sys.I_base = sys.S_base / (sqrt(3) * sys.V_LL);
    sys.Z_base = (sys.V_LL^2) / sys.S_base;

    %% 2. SOURCE IMPEDANCE (Substation Stiffness)
    % A stiff source (high SC MVA) means very high current at the start.
    MVA_SC = 250e6; % Short Circuit MVA capacity of substation
    Z_source_mag = sys.S_base / MVA_SC; 
    
    % Source is usually inductive (X/R approx 8 to 10)
    sys.Z_source = Z_source_mag * (0.1 + 0.99j); % Simplified PU

    %% 3. LINE CONDUCTOR PARAMETERS (Per Kilometer)
    % Values for typical ACSR distribution wire (e.g., #2/0 AWG)
    % These must be in PER UNIT (PU) / km
    
    % Positive Sequence (R1 + jX1) - Ohms/km
    R1_ohm = 0.19; 
    X1_ohm = 0.40;
    
    % Zero Sequence (R0 + jX0) - Ohms/km (Usually 3x higher)
    R0_ohm = 0.50; 
    X0_ohm = 1.20;
    
    % Convert to PU/km
    sys.z1_pu_km = (R1_ohm + 1j*X1_ohm) / sys.Z_base;
    sys.z0_pu_km = (R0_ohm + 1j*X0_ohm) / sys.Z_base;

    %% 4. OVERWATCH UNIT DEPLOYMENT
    % Distance of each unit from the substation (in km)
    sys.unit_locations_km = [0.0, 2.0, 5.0, 8.0]; 
    
    % GPS Coordinates [Lat, Long] for visualization output later
    sys.unit_gps = [
        13.141, 123.741; % Unit 1
        13.155, 123.755; % Unit 2
        13.170, 123.770  % Unit 3
    ];
end