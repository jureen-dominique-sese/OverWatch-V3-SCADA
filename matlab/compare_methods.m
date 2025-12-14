%% COMPARISON: Lookup Table vs Impedance Method
clear; clc;

fprintf('╔════════════════════════════════════════════════════════╗\n');
fprintf('║    METHOD COMPARISON: Lookup vs Impedance-Based       ║\n');
fprintf('╚════════════════════════════════════════════════════════╝\n\n');

% Test scenarios
test_cases = [
    0.5, 1;   % 0.5 km, SLG
    2.5, 1;   % 2.5 km, SLG
    5.0, 1;   % 5.0 km, SLG
    7.5, 1;   % 7.5 km, SLG
    3.0, 2;   % 3.0 km, LL
    6.0, 2;   % 6.0 km, LL
    4.0, 3;   % 4.0 km, 3PH
    8.0, 3;   % 8.0 km, 3PH
];

% Storage for results
results_table = [];

for i = 1:size(test_cases, 1)
    actual_dist = test_cases(i, 1);
    fault_type = test_cases(i, 2);
    
    fprintf('\n──────────────────────────────────────────────────────\n');
    fprintf('Test %d: Fault at %.2f km, Type %d\n', i, actual_dist, fault_type);
    fprintf('──────────────────────────────────────────────────────\n');
    
    % METHOD 1: LOOKUP TABLE (Your Current Method)
    sensor_data = simulate_overwatch_network(actual_dist, fault_type);
    result_lookup = cpu_fault_locator(sensor_data.readings);
    
    est_lookup = result_lookup.location;
    error_lookup = abs(est_lookup - actual_dist) * 1000;  % meters
    
    % METHOD 2: IMPEDANCE-BASED
    % We need to calculate V and I at the substation (distance = 0)
    % For this, we simulate what the relay sees
    [V_relay, I_relay] = simulate_relay_measurements(actual_dist, fault_type);
    
    est_impedance = impedance_fault_locator(V_relay, I_relay, fault_type);
    error_impedance = abs(est_impedance - actual_dist) * 1000;  % meters
    
    % Display comparison
    fprintf('  Actual Location:       %.3f km\n', actual_dist);
    fprintf('  ┌─ Lookup Method:      %.3f km  (Error: %.1f m)\n', est_lookup, error_lookup);
    fprintf('  └─ Impedance Method:   %.3f km  (Error: %.1f m)\n', est_impedance, error_impedance);
    
    % Determine winner
    if error_lookup < error_impedance
        fprintf('  ✓ Winner: Lookup Table (%.1f m better)\n', error_impedance - error_lookup);
        winner = 'Lookup';
    else
        fprintf('  ✓ Winner: Impedance (%.1f m better)\n', error_lookup - error_impedance);
        winner = 'Impedance';
    end
    
    % Store results
    results_table = [results_table; actual_dist, fault_type, ...
                     est_lookup, error_lookup, ...
                     est_impedance, error_impedance];
end

%% SUMMARY STATISTICS
fprintf('\n\n╔════════════════════════════════════════════════════════╗\n');
fprintf('║                   SUMMARY STATISTICS                   ║\n');
fprintf('╚════════════════════════════════════════════════════════╝\n\n');

avg_error_lookup = mean(results_table(:, 4));
avg_error_impedance = mean(results_table(:, 6));

max_error_lookup = max(results_table(:, 4));
max_error_impedance = max(results_table(:, 6));

fprintf('  LOOKUP TABLE METHOD:\n');
fprintf('    Average Error:  %.2f meters\n', avg_error_lookup);
fprintf('    Maximum Error:  %.2f meters\n', max_error_lookup);
fprintf('    Std Deviation:  %.2f meters\n\n', std(results_table(:, 4)));

fprintf('  IMPEDANCE METHOD:\n');
fprintf('    Average Error:  %.2f meters\n', avg_error_impedance);
fprintf('    Maximum Error:  %.2f meters\n', max_error_impedance);
fprintf('    Std Deviation:  %.2f meters\n\n', std(results_table(:, 6)));

if avg_error_lookup < avg_error_impedance
    improvement = ((avg_error_impedance - avg_error_lookup) / avg_error_impedance) * 100;
    fprintf('  🏆 LOOKUP METHOD IS %.1f%% MORE ACCURATE!\n', improvement);
else
    improvement = ((avg_error_lookup - avg_error_impedance) / avg_error_lookup) * 100;
    fprintf('  🏆 IMPEDANCE METHOD IS %.1f%% MORE ACCURATE!\n', improvement);
end

%% GENERATE COMPARISON PLOT
figure(1);
subplot(2,1,1);
bar([results_table(:,4), results_table(:,6)]);
title('Error Comparison: Lookup vs Impedance');
xlabel('Test Case');
ylabel('Error (meters)');
legend('Lookup Table', 'Impedance-Based');
grid on;

subplot(2,1,2);
plot(results_table(:,1), results_table(:,3), 'bo-', 'LineWidth', 2, 'MarkerSize', 8);
hold on;
plot(results_table(:,1), results_table(:,5), 'rs-', 'LineWidth', 2, 'MarkerSize', 8);
plot(results_table(:,1), results_table(:,1), 'k--', 'LineWidth', 1.5);
xlabel('Actual Distance (km)');
ylabel('Estimated Distance (km)');
title('Accuracy Comparison');
legend('Lookup Method', 'Impedance Method', 'Perfect Accuracy', 'Location', 'southeast');
grid on;

fprintf('\n📊 Comparison plots generated!\n');
% Add to end of compare_methods.m

fprintf('\n\n=== TABLE FOR THESIS ===\n');
fprintf('Distance | Fault Type | Lookup Error | Impedance Error | Improvement\n');
fprintf('---------|------------|--------------|-----------------|------------\n');

for i = 1:size(results_table, 1)
    improvement = results_table(i,6) - results_table(i,4);
    fprintf('%7.1f km | Type %d     | %10.1f m | %13.1f m | %+9.1f m\n', ...
            results_table(i,1), results_table(i,2), ...
            results_table(i,4), results_table(i,6), improvement);
end