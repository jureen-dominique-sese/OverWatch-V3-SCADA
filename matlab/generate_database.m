function generate_database()
% GENERATE_DATABASE
% Creates 'Fault_Lookup_Table.mat'
% Simulates faults every 10 meters (0.01km) to create the Ground Truth.

    fprintf('Generating Theoretical Data... ');
    
    max_len = 55.0; % 50 km line
    step = 0.01;    % 10 meter resolution
    distances = step:step:max_len;
    
    % Initialize Tables
    % Columns: [Distance_km, Ia, Ib, Ic]
    data_SLG = [];
    data_LL = [];
    data_3PH = [];
    
    for d = distances
        % 1. Simulate SLG
        I_slg = calculate_fault_current(d, 1, 0);
        data_SLG = [data_SLG; d, I_slg(1), I_slg(2), I_slg(3)];
        
        % 2. Simulate LL
        I_ll = calculate_fault_current(d, 2, 0);
        data_LL = [data_LL; d, I_ll(1), I_ll(2), I_ll(3)];
        
        % 3. Simulate 3PH
        I_3ph = calculate_fault_current(d, 3, 0);
        data_3PH = [data_3PH; d, I_3ph(1), I_3ph(2), I_3ph(3)];
    end
    
    % Save specific variables
% --- NEW CSV EXPORT WITH HEADERS (Octave Compatible) ---
    % 1. Prepare the data matrix
    data_SLG_tagged = [data_SLG, ones(size(data_SLG,1), 1) * 1];
    data_LL_tagged  = [data_LL,  ones(size(data_LL,1), 1) * 2];
    data_3PH_tagged = [data_3PH, ones(size(data_3PH,1), 1) * 3];

    full_table = [data_SLG_tagged; data_LL_tagged; data_3PH_tagged];

    % 2. Write the Header Row
    fid = fopen('Fault_Lookup_Table.csv', 'w');
    fprintf(fid, 'Distance_km,Ia,Ib,Ic,Fault_Type\n');
    fclose(fid);

    % 3. Append the Numeric Data
    % '-append' adds to the file without overwriting the header
    dlmwrite('Fault_Lookup_Table.csv', full_table, '-append', 'precision', '%.4f');
    
    fprintf('Done! Database Saved as Fault_Lookup_Table.csv (with headers).\n');
end