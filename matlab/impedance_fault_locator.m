function distance_km = impedance_fault_locator(V_measured, I_measured, fault_type)
% IMPEDANCE_FAULT_LOCATOR
% Traditional impedance-based fault location method
%
% INPUTS:
%   V_measured: Complex voltage at relay point (pu or actual)
%   I_measured: Complex current at relay point (pu or actual)
%   fault_type: 1=SLG, 2=LL, 3=3PH
%
% OUTPUT:
%   distance_km: Estimated fault distance

    sys = get_system_config();
    
    % Calculate apparent impedance
    Z_apparent = V_measured / I_measured;
    
    % Remove source impedance
    Z_line = Z_apparent - sys.Z_source;
    
    % Select appropriate line impedance based on fault type
    if fault_type == 1  % SLG
        % For ground faults, use composite impedance
        z_per_km = sys.z1_pu_km + 2*sys.z0_pu_km;
        
    elseif fault_type == 2  % LL
        % For line-to-line, current flows through 2 phases
        z_per_km = 2 * sys.z1_pu_km;
        
    elseif fault_type == 3  % 3PH
        % For balanced 3-phase, use positive sequence only
        z_per_km = sys.z1_pu_km;
    end
    
    % Calculate distance
    distance_km = abs(Z_line) / abs(z_per_km);
    
end