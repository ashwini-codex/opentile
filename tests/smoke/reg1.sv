// 1-bit synchronous register used only as an O0 toolchain smoke.
`default_nettype none

module reg1 (
    input  logic clk,
    input  logic rst_n,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk) begin
        if (!rst_n) q <= 1'b0;
        else        q <= d;
    end

    // Trivial safety property for SBY: q is a defined 1-bit value.
    always_comb begin
        assert (q === 1'b0 || q === 1'b1);
    end
endmodule

`default_nettype wire
