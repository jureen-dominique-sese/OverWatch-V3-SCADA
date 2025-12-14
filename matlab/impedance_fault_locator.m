function distance_km = impedance_fault_locator(V_measured, I_measured, fault_type)
% IMPEDANCE_FAULT_LOCATOR
% Calculates distance based on V/I and line parameters.
% Input V and I must be complex PU.

    sys = get_system_config();
    
    % Check for zero current to avoid NaN
    if abs(I_measured) < 1e-5
        distance_km = 0;
        return;
    end
    
    % 1. Calculate Apparent Impedance (Z_seen)
    Z_seen = V_measured / I_measured;
    
    % 2. Determine Line Impedance Characteristic (z_per_km)
    % This depends on the loop we measured.
    
    if fault_type == 1  % SLG (Phase A-G)
        % The loop impedance for Phase-Ground involves Z0.
        % Mathematical derivation matches: (2*Z1 + Z0) / 3
        z_per_km = (2*sys.z1_pu_km + sys.z0_pu_km) / 3;
        
    elseif fault_type == 2  % LL (Phase B-C)
        % We measured Phase B V/I.
        % In a B-C fault, the impedance seen by Phase B relay is approx Z1.
        % (Strictly V_LL/I_LL = 2*Z1, but V_ph/I_ph approx Z1 in this balanced setup)
        z_per_km = sys.z1_pu_km;
        
    elseif fault_type == 3  % 3PH
        % Balanced 3-phase sees positive sequence impedance
        z_per_km = sys.z1_pu_km;
    end
    
    % 3. Calculate Distance
    distance_km = abs(Z_seen) / abs(z_per_km);
    
end