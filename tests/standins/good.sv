// Behavioural tile_top stand-in: real ports, GEMM from streams, spec state timing.
`default_nettype none

module tile_top #(
    parameter int R     = 4,
    parameter int C     = 4,
    parameter int K_MAX = 64
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic [15:0]          cfg_k_i,
    input  logic                 start_i,
    output logic                 busy_o,
    output logic                 done_o,
    output logic                 err_o,
    output logic [2:0]           err_code_o,
    input  logic signed [7:0]    s_axis_a_tdata,
    input  logic                 s_axis_a_tvalid,
    output logic                 s_axis_a_tready,
    input  logic                 s_axis_a_tlast,
    input  logic signed [7:0]    s_axis_b_tdata,
    input  logic                 s_axis_b_tvalid,
    output logic                 s_axis_b_tready,
    input  logic                 s_axis_b_tlast,
    output logic signed [31:0]   m_axis_c_tdata,
    output logic                 m_axis_c_tvalid,
    input  logic                 m_axis_c_tready,
    output logic                 m_axis_c_tlast
);
    typedef enum logic [2:0] {ST_IDLE, ST_LOAD, ST_COMPUTE, ST_DRAIN, ST_STORE} state_t;
    state_t state;

    logic [15:0] k_q;
    int unsigned a_count, b_count, c_count, comp_left;

    logic signed [7:0]  mem_a [0:R-1][0:K_MAX-1];
    logic signed [7:0]  mem_b [0:K_MAX-1][0:C-1];
    logic signed [31:0] mem_c [0:R*C-1];

    assign err_o  = |err_code_o;
    assign busy_o = (state != ST_IDLE);

    wire k_ok = (cfg_k_i >= 16'd1) && (cfg_k_i <= K_MAX[15:0]);

    always_comb begin
        s_axis_a_tready = (state == ST_LOAD) && (a_count < R * k_q);
        s_axis_b_tready = (state == ST_LOAD) && (b_count < C * k_q);
        m_axis_c_tvalid = (state == ST_STORE);
        m_axis_c_tdata  = mem_c[c_count];
        m_axis_c_tlast  = (state == ST_STORE) && (c_count == R * C - 1);
    end

    integer i, j, kk;
    logic signed [31:0] acc;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state      <= ST_IDLE;
            done_o     <= 1'b0;
            err_code_o <= 3'b000;
            k_q        <= 16'd1;
            a_count    <= 0;
            b_count    <= 0;
            c_count    <= 0;
            comp_left  <= 0;
        end else begin
            done_o <= 1'b0;
            unique case (state)
                ST_IDLE: begin
                    a_count <= 0;
                    b_count <= 0;
                    c_count <= 0;
                    if (start_i) begin
                        if (k_ok) begin
                            k_q        <= cfg_k_i;
                            err_code_o <= 3'b000;
                            state      <= ST_LOAD;
                        end else begin
                            err_code_o[0] <= 1'b1;
                        end
                    end
                end
                ST_LOAD: begin
                    if (s_axis_a_tvalid && s_axis_a_tready) begin
                        mem_a[a_count / k_q][a_count % k_q] <= s_axis_a_tdata;
                        if (s_axis_a_tlast != (a_count == R * k_q - 1))
                            err_code_o[1] <= 1'b1;
                        a_count <= a_count + 1;
                    end
                    if (s_axis_b_tvalid && s_axis_b_tready) begin
                        mem_b[b_count / C][b_count % C] <= s_axis_b_tdata;
                        if (s_axis_b_tlast != (b_count == C * k_q - 1))
                            err_code_o[2] <= 1'b1;
                        b_count <= b_count + 1;
                    end
                    if ((a_count + ((s_axis_a_tvalid && s_axis_a_tready) ? 1 : 0) >= R * k_q) &&
                        (b_count + ((s_axis_b_tvalid && s_axis_b_tready) ? 1 : 0) >= C * k_q)) begin
                        state     <= ST_COMPUTE;
                        comp_left <= k_q + R + C - 2;
                    end
                end
                ST_COMPUTE: begin
                    if (comp_left == k_q + R + C - 2) begin
                        for (i = 0; i < R; i = i + 1) begin
                            for (j = 0; j < C; j = j + 1) begin
                                acc = 32'sd0;
                                for (kk = 0; kk < K_MAX; kk = kk + 1) begin
                                    if (kk < k_q)
                                        acc = acc + 32'(mem_a[i][kk]) * 32'(mem_b[kk][j]);
                                end
                                mem_c[i * C + j] <= acc;
                            end
                        end
                    end
                    if (comp_left <= 1) begin
                        state <= ST_DRAIN;
                    end else begin
                        comp_left <= comp_left - 1;
                    end
                end
                ST_DRAIN: begin
                    state   <= ST_STORE;
                    c_count <= 0;
                end
                ST_STORE: begin
                    if (m_axis_c_tvalid && m_axis_c_tready) begin
                        if (c_count == R * C - 1) begin
                            state  <= ST_IDLE;
                            done_o <= 1'b1;
                        end else begin
                            c_count <= c_count + 1;
                        end
                    end
                end
                default: state <= ST_IDLE;
            endcase
        end
    end
endmodule

`default_nettype wire
