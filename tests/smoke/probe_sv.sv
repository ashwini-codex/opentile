// Probe: generate, signed arithmetic, packed arrays, always_ff.
// Used only to see whether Yosys `read_verilog -sv` accepts the SV subset OpenTile needs.
`default_nettype none

module probe_sv (
    input  logic               clk,
    input  logic               rst_n,
    input  logic signed  [7:0] a,
    input  logic signed  [7:0] b,
    output logic signed [31:0] acc,
    output logic         [3:0] packed_q
);
    logic signed [7:0] pipe [0:3];
    genvar i;
    generate
        for (i = 0; i < 4; i++) begin : g_pipe
            if (i == 0) begin : g_head
                always_ff @(posedge clk) begin
                    if (!rst_n) pipe[i] <= '0;
                    else        pipe[i] <= a;
                end
            end else begin : g_tail
                always_ff @(posedge clk) begin
                    if (!rst_n) pipe[i] <= '0;
                    else        pipe[i] <= pipe[i-1];
                end
            end
        end
    endgenerate

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            acc      <= '0;
            packed_q <= '0;
        end else begin
            acc      <= acc + a * b;
            packed_q <= {packed_q[2:0], a[0]};
        end
    end
endmodule

`default_nettype wire
