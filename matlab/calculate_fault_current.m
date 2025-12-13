function currents = calculate_fault_current(fault_dist_km, fault_type, Rf_ohms)
% CALCULATE_FAULT_CURRENT
% Returns the Phase Currents [Ia, Ib, Ic] for a fault at a specific distance.
% 
% INPUTS:
%   fault_dist_km: Distance to fault
%   fault_type:    1='SLG', 2='LL', 3='3PH'
%   Rf_ohms:       Fault Resistance (0 for bolted)

    sys = get_system_config();
    
    % 1. Total Impedance Calculation (Source + Line)
    Z1_total = sys.Z_source + (sys.z1_pu_km * fault_dist_km);
    Z2_total = Z1_total; % Assume Z2 = Z1
    Z0_total = sys.Z_source + (sys.z0_pu_km * fault_dist_km);
    
    % Convert Rf to PU
    Rf_pu = Rf_ohms / sys.Z_base;
    
    % Pre-fault Voltage (1.0 pu)
    V_f = 1.0;
    a = -0.5 + 1j*0.866; % The 120-degree operator
    
    % 2. Sequence Currents Calculation (Symmetrical Components)
    I0 = 0; I1 = 0; I2 = 0;
    
    if fault_type == 1 % SLG (Phase A to Ground)
        denom = Z1_total + Z2_total + Z0_total + (3 * Rf_pu);
        I1 = V_f / denom;
        I2 = I1;
        I0 = I1;
        
    elseif fault_type == 2 % LL (Phase B to C)
        I1 = V_f / (Z1_total + Z2_total + Rf_pu);
        I2 = -I1;
        I0 = 0;
        
    elseif fault_type == 3 % 3PH (Balanced)
        I1 = V_f / (Z1_total + Rf_pu);
        I2 = 0;
        I0 = 0;
    end
    
    % 3. Convert Sequence to Phase Currents
    % [Ia; Ib; Ic] = A_matrix * [I0; I1; I2]
    A_mat = [1 1 1; 1 a^2 a; 1 a a^2];
    I_seq = [I0; I1; I2];
    I_phase_pu = A_mat * I_seq;
    
    % 4. Convert PU to Actual Amps
    I_phase_actual = abs(I_phase_pu) * sys.I_base;
    
    % Return vector [Ia, Ib, Ic]
    currents = I_phase_actual;
end