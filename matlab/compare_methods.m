    %% COMPARISON: [Simulation] Fault Lookup Table vs Impedance Based Method
    % OCTAVE COMPATIBLE VERSION
    % Automatically regenerates the Reference Database before testing.

    clear; clc;

    %% --- STEP 0: USER INPUT CONFIGURATION ---
    fprintf('=== SIMULATION SETUP ===\n');
    % 1. Get Line Length
    user_len = input('Enter Maximum Line Length (km) [Default: 50]: ');
    if isempty(user_len)
        max_len = 50.0; 
    else
        max_len = double(user_len);
    end

    % 2. Get Sample Size
    user_tests = input('Enter Number of Test Cases [Default: 1000]: ');
    if isempty(user_tests)
        num_tests = 1000;
    else
        num_tests = double(user_tests);
    end

    fprintf('\nConfiguration Set: %.1f km line, %d test cases.\n\n', max_len, num_tests);


    fprintf('╔════════════════════════════════════════════════════════╗\n');
    fprintf('║   [Simulation] Fault Lookup Table vs Impedance Method  ║\n');
    fprintf('╠════════════════════════════════════════════════════════╣\n');
    fprintf('║ EXPERIMENTAL CONDITIONS:                               ║\n');
    fprintf('║ 1. Ground Truth: Auto-generated before test run.       ║\n');
    fprintf('║ 2. Sample Size: %-6d Randomized Test Cases.            ║\n', num_tests);
    fprintf('║ 3. Noise: +/- 1%% Random Sensor Error Injected.       ║\n');
    fprintf('╚════════════════════════════════════════════════════════╝\n\n');

    %% --- STEP 1: GENERATE REFERENCE DATABASE (Ground Truth) ---
    fprintf('Step 1: Generating fresh Fault Lookup Table (0 - %.1f km)... ', max_len);

    % Simulation parameters for the database
    step = 0.01;    % 10 meter resolution
    distances = step:step:max_len;

    % Initialize Tables
    data_SLG = [];
    data_LL = [];
    data_3PH = [];

    % Generate perfect theoretical values for every 10m
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

    % Save the database so cpu_fault_locator can use it
    save('Fault_Lookup_Table.mat', 'data_SLG', 'data_LL', 'data_3PH');
    fprintf('Done! Database Updated.\n');


    %% --- STEP 2: GENERATE RANDOM TEST CASES ---
    min_dist = 0.1;
    max_dist = max_len;

    % Set seed for reproducibility
    rand('seed', 42); 

    % Generate Random Distances
    random_dists = min_dist + (max_dist - min_dist) .* rand(num_tests, 1);

    % Generate Random Fault Types (1=SLG, 2=LL, 3=3PH)
    random_types = floor(1 + (3-1+1) * rand(num_tests, 1));

    test_cases = [random_dists, random_types];
    results_table = [];

    fprintf('Running %d simulations with noise injection... Please wait.\n', num_tests);

   %% --- STEP 3: RUN SIMULATION LOOP ---
for i = 1:num_tests
    actual_dist = test_cases(i, 1);
    fault_type = test_cases(i, 2);
    
    % METHOD 1: LOOKUP TABLE (Overwatch)
    % [UPDATED] Capture the noise percentage returned by the function
    [sensor_data, noise_pct] = simulate_overwatch_network(actual_dist, fault_type);
    
    result_lookup = cpu_fault_locator(sensor_data.readings);
    
    est_lookup = result_lookup.location;
    error_lookup = abs(est_lookup - actual_dist) * 1000;  % Convert to meters
    
    % Retrieve Actual Lookup Table Value (Theoretical)
    if fault_type == 1 % SLG
        tbl = data_SLG; col = 2; % Ia
    elseif fault_type == 2 % LL
        tbl = data_LL; col = 3; % Ib
    else % 3PH
        tbl = data_3PH; col = 2; % Ia
    end
    
    lookup_idx = round(est_lookup / step);
    if lookup_idx < 1, lookup_idx = 1; end
    if lookup_idx > size(tbl, 1), lookup_idx = size(tbl, 1); end
    
    lookup_I_theory = tbl(lookup_idx, col);
    
    
    % METHOD 2: IMPEDANCE-BASED (Traditional)
    [V_relay, I_relay] = simulate_relay_measurements(actual_dist, fault_type);
    est_impedance = impedance_fault_locator(V_relay, I_relay, fault_type);
    error_impedance = abs(est_impedance - actual_dist) * 1000;  % Convert to meters
    
    % Calculate Impedance Mag
    if abs(I_relay) > 0
        calc_Z_mag = abs(V_relay / I_relay);
    else
        calc_Z_mag = 0;
    end
    
    % Calculate % Error
    pct_err_lookup = (error_lookup / (actual_dist*1000)) * 100;
    pct_err_imp = (error_impedance / (actual_dist*1000)) * 100;
    
    % Store Results (Added noise_pct at the end, col 12)
    results_table = [results_table; 
                     actual_dist, fault_type, ...
                     est_lookup, error_lookup, lookup_I_theory, lookup_idx, ...
                     est_impedance, error_impedance, calc_Z_mag, ...
                     pct_err_lookup, pct_err_imp, noise_pct];
end

    %% --- STEP 4: CALCULATE STATISTICS ---
    % Update Indices due to new columns
    % Err_L is col 4, Err_I is col 8
    % %_L is col 10, %_I is col 11

    avg_err_L = mean(results_table(:, 4));
    avg_err_I = mean(results_table(:, 8));
    max_err_L = max(results_table(:, 4));
    max_err_I = max(results_table(:, 8));
    mape_L = mean(results_table(:, 10));
    mape_I = mean(results_table(:, 11));

    % Win Rates
    wins_L = sum(results_table(:,4) < results_table(:,8));
    win_rate_L = (wins_L / num_tests) * 100;

    % Group by Fault Type
    idx1 = find(results_table(:,2) == 1);
    avg_err_L_1 = mean(results_table(idx1, 4));
    avg_err_I_1 = mean(results_table(idx1, 8));

    idx2 = find(results_table(:,2) == 2);
    avg_err_L_2 = mean(results_table(idx2, 4));
    avg_err_I_2 = mean(results_table(idx2, 8));

    idx3 = find(results_table(:,2) == 3);
    avg_err_L_3 = mean(results_table(idx3, 4));
    avg_err_I_3 = mean(results_table(idx3, 8));


    %% --- STEP 5: GENERATE PLOTS (Octave Compatible) ---
    figure(1);
    clf;

    % Subplot 1: Error Distribution
    subplot(2,2,1);
    [nL, xL] = hist(results_table(:,4), 15);
    [nI, xI] = hist(results_table(:,8), 15);
    plot(xL, nL, 'b-o', 'LineWidth', 2); hold on;
    plot(xI, nI, 'r-s', 'LineWidth', 2);
    title('Error Distribution (Freq)');
    xlabel('Error (meters)'); ylabel('Count');
    legend('Lookup Table', 'Impedance Method');
    grid on;

    % Subplot 2: Error vs Distance Scatter
    subplot(2,2,2);
    plot(results_table(:,1), results_table(:,4), 'bo', 'MarkerFaceColor', 'b', 'MarkerSize', 4);
    hold on;
    plot(results_table(:,1), results_table(:,8), 'rs', 'MarkerFaceColor', 'r', 'MarkerSize', 4);
    title('Error vs. Distance');
    xlabel('Distance (km)'); ylabel('Error (meters)');
    legend('Lookup', 'Impedance');
    grid on;

    % Subplot 3: Bar Chart by Fault Type
    subplot(2,1,2);
    y = [avg_err_L_1, avg_err_I_1; avg_err_L_2, avg_err_I_2; avg_err_L_3, avg_err_I_3];
    bar(y);
    set(gca, 'XTickLabel', {'SLG', 'LL', '3PH'});
    title('Average Error by Fault Type');
    ylabel('Mean Error (meters)');
    legend('Lookup Table', 'Impedance Method');
    grid on;

    fprintf('\n📊 Plots generated in Figure 1.\n');


  %% --- STEP 6: PRINT TABLES TO TERMINAL ---

fprintf('\n\n');
fprintf('==================================================================================================================================\n');
fprintf('                                            TABLE 1: DETAILED TEST RESULTS                                                        \n');
fprintf('==================================================================================================================================\n');
% [UPDATED] Header now includes "Inj.Noise(%)" between Lookup(km) and Lookup Ref
fprintf(' ID | Dist(km) | Type | Lookup(km) | Inj.Noise(%%) | Lookup Ref(A) (Row#) | Lookup Err(m) | Imped(km) | Calc Z(Ω) | Imped Err(m) \n');
fprintf('----|----------|------|------------|--------------|----------------------|---------------|-----------|-----------|--------------\n');

print_limit = min(num_tests, 50); 
for i = 1:print_limit
    
    % [UPDATED] Format string includes the noise column (results_table(i,12))
    fprintf('%3d | %8.3f |  %d   |  %8.3f  |   %6.2f%%    | %9.2f A (#%5d) | %9.2f m   | %9.3f | %8.2fΩ | %9.2f m \n', ...
            i, results_table(i,1), results_table(i,2), ...
            results_table(i,3), ...                  % Est Lookup Dist
            results_table(i,12), ...                 % [NEW] Injected Noise %
            results_table(i,5), results_table(i,6), ... % Ref Current & Row Index
            results_table(i,4), ...                  % Lookup Error
            results_table(i,7), ...                  % Est Imped Dist
            results_table(i,9), ...                  % Calc Z
            results_table(i,8));                     % Imped Error
end
if num_tests > print_limit
    fprintf('... (Showing first %d of %d tests) ...\n', print_limit, num_tests);
end

    fprintf('\n\n');
    fprintf('========================================================================================\n');
    fprintf('                       TABLE 2: PERFORMANCE SUMMARY (AGGREGATED)                        \n');
    fprintf('========================================================================================\n');
    fprintf(' METRIC                     | LOOKUP TABLE METHOD       | IMPEDANCE METHOD             \n');
    fprintf('----------------------------|---------------------------|------------------------------\n');
    fprintf(' Mean Absolute Error (MAE)  | %10.2f meters         | %10.2f meters\n', avg_err_L, avg_err_I);
    fprintf(' Max Recorded Error         | %10.2f meters         | %10.2f meters\n', max_err_L, max_err_I);
    fprintf(' Mean %% Error (MAPE)       | %10.2f %%              | %10.2f %%\n', mape_L, mape_I);
    fprintf(' Standard Deviation         | %10.2f meters         | %10.2f meters\n', std(results_table(:,4)), std(results_table(:,8)));
    fprintf(' Win Rate (Cases Won)       | %9.1f %%               | %9.1f %%\n', win_rate_L, 100-win_rate_L);
    fprintf('----------------------------|---------------------------|------------------------------\n');


    fprintf('\n\n');
    fprintf('========================================================================================\n');
    fprintf('                       TABLE 3: ACCURACY BY FAULT TYPE (BREAKDOWN)                      \n');
    fprintf('========================================================================================\n');
    fprintf(' FAULT TYPE      | Lookup Avg Error | Impedance Avg Error | Improvement (+/-) \n');
    fprintf('-----------------|------------------|---------------------|-------------------\n');

    % Row 1: SLG
    imp_1 = avg_err_I_1 - avg_err_L_1;
    if imp_1 > 0, s1='+'; winner1='Lookup better'; else, s1=''; winner1='Impedance better'; end
    fprintf(' SLG (1-Phase)   | %10.2f m     | %13.2f m      | %s%.2f m (%s)\n', ...
        avg_err_L_1, avg_err_I_1, s1, imp_1, winner1);

    % Row 2: LL
    imp_2 = avg_err_I_2 - avg_err_L_2;
    if imp_2 > 0, s2='+'; else, s2=''; end
    fprintf(' LL (2-Phase)    | %10.2f m     | %13.2f m      | %s%.2f m\n', ...
        avg_err_L_2, avg_err_I_2, s2, imp_2);

    % Row 3: 3PH
    imp_3 = avg_err_I_3 - avg_err_L_3;
    if imp_3 > 0, s3='+'; else, s3=''; end
    fprintf(' 3PH (Balanced)  | %10.2f m     | %13.2f m      | %s%.2f m\n', ...
        avg_err_L_3, avg_err_I_3, s3, imp_3);
    fprintf('-----------------|------------------|---------------------|-------------------\n');

    % Final Verdict
    fprintf('\n>>> FINAL VERDICT: \n');
    if avg_err_L < avg_err_I
        improvement = ((avg_err_I - avg_err_L) / avg_err_I) * 100;
        fprintf('  🏆 PROPOSED LOOKUP TABLE METHOD OUTPERFORMS TRADITIONAL METHOD.\n');
        fprintf('     - Average Accuracy Improvement: %.2f%%\n', improvement);
        fprintf('     - Total Victories: %d out of %d test cases (%.1f%% Win Rate)\n', wins_L, num_tests, win_rate_L);
    else
        improvement = ((avg_err_L - avg_err_I) / avg_err_L) * 100;
        wins_I = num_tests - wins_L;
        win_rate_I = 100 - win_rate_L;
        fprintf('  🏆 TRADITIONAL IMPEDANCE METHOD OUTPERFORMS LOOKUP TABLE.\n');
        fprintf('     - Average Accuracy Improvement: %.2f%%\n', improvement);
        fprintf('     - Total Victories: %d out of %d test cases (%.1f%% Win Rate)\n', wins_I, num_tests, win_rate_I);
    end

    fprintf('\n\n');
    fprintf('========================================================================================\n');
    fprintf('                          STRATEGIC ANALYSIS & CONCLUSION                               \n');
    fprintf('========================================================================================\n');
    fprintf('1. COMPARATIVE DISCREPANCY ANALYSIS:\n');
    fprintf('   - The [Impedance Method] offers infinite theoretical resolution but is highly\n');
    fprintf('     sensitive to sensor noise, causing error scaling at long distances.\n');
    fprintf('   - The [Lookup Table Method] is robust against noise but limited by grid steps.\n');
    fprintf('   - CROSSOVER POINT: Impedance wins at short range; Lookup wins at long range.\n\n');


    %% --- STEP 7: EXPORT FULL REPORT TO CSV (EXCEL) ---
    fprintf('\n========================================================================================\n');
    fprintf('                              EXPORTING FULL REPORT TO EXCEL (CSV)                      \n');
    fprintf('========================================================================================\n');

    csv_filename = 'Simulation_Results.csv';
    fid = fopen(csv_filename, 'w');

    if fid ~= -1
        % --- SECTION 1: DETAILED TEST CASES ---
        fprintf(fid, 'TABLE 1: DETAILED TEST RESULTS\n');
        % Updated Header to include new columns
        fprintf(fid, 'ID,Actual_Dist_km,Fault_Type,Est_Lookup_km,Lookup_Ref_Current_A,Lookup_Ref_Row_Index,Err_Lookup_m,Est_Imped_km,Calc_Impedance_Ohms,Err_Imped_m,Pct_Err_Lookup,Pct_Err_Imped\n');
        
        % Manually write rows to handle mixed types/clean formatting if needed, but dlmwrite is faster for pure numbers
        % We will prep a matrix with ID for export
        export_matrix = [(1:num_tests)', results_table];
        fclose(fid);
        
        % Append the data matrix
        dlmwrite(csv_filename, export_matrix, '-append', 'precision', '%.4f');
        
        % Re-open to append the Summary Tables
        fid = fopen(csv_filename, 'a');
        
        % --- SECTION 2: PERFORMANCE SUMMARY ---
        fprintf(fid, '\n\nTABLE 2: PERFORMANCE SUMMARY (AGGREGATED)\n');
        fprintf(fid, 'Metric,Lookup_Table_Method,Impedance_Method\n');
        fprintf(fid, 'Mean_Abs_Error_(m),%.2f,%.2f\n', avg_err_L, avg_err_I);
        fprintf(fid, 'Max_Error_(m),%.2f,%.2f\n', max_err_L, max_err_I);
        fprintf(fid, 'MAPE_(%%),%.2f,%.2f\n', mape_L, mape_I);
        fprintf(fid, 'Std_Deviation_(m),%.2f,%.2f\n', std(results_table(:,4)), std(results_table(:,8)));
        fprintf(fid, 'Win_Rate_(%%),%.1f,%.1f\n', win_rate_L, 100-win_rate_L);
        
        % --- SECTION 3: ACCURACY BY FAULT TYPE ---
        fprintf(fid, '\n\nTABLE 3: ACCURACY BY FAULT TYPE\n');
        fprintf(fid, 'Fault_Type,Lookup_Avg_Err_(m),Impedance_Avg_Err_(m),Difference_(m)\n');
        fprintf(fid, 'SLG (1-Phase),%.2f,%.2f,%.2f\n', avg_err_L_1, avg_err_I_1, avg_err_I_1 - avg_err_L_1);
        fprintf(fid, 'LL (2-Phase),%.2f,%.2f,%.2f\n', avg_err_L_2, avg_err_I_2, avg_err_I_2 - avg_err_L_2);
        fprintf(fid, '3PH (Balanced),%.2f,%.2f,%.2f\n', avg_err_L_3, avg_err_I_3, avg_err_I_3 - avg_err_L_3);
        
        fclose(fid);
        
        fprintf('  ✅ Success! Full report saved to: %s\n', csv_filename);
        fprintf('  This file contains all test cases + summary tables at the bottom.\n');
    else
        fprintf('  ❌ Error: Could not open file for writing.\n');
    end