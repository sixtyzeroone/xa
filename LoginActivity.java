package com.vortexstore.ui.auth;

import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.gms.auth.api.signin.GoogleSignIn;
import com.google.android.gms.auth.api.signin.GoogleSignInAccount;
import com.google.android.gms.auth.api.signin.GoogleSignInClient;
import com.google.android.gms.auth.api.signin.GoogleSignInOptions;
import com.google.android.gms.auth.api.signin.GoogleSignInStatusCodes;
import com.google.android.gms.common.api.ApiException;
import com.google.android.gms.tasks.Task;
import com.google.firebase.auth.AuthCredential;
import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseUser;
import com.google.firebase.auth.GoogleAuthProvider;
import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;
import com.vortexstore.R;
import com.vortexstore.models.User;
import com.vortexstore.ui.dashboard.DashboardActivity;

public class LoginActivity extends AppCompatActivity {
    private static final int RC_SIGN_IN = 9001;

    private EditText etPhoneNumber;
    private Button btnContinueWithWhatsApp, btnGoogleSignIn;
    private ProgressBar progressBar;
    private TextView tvRegister;

    private FirebaseAuth mAuth;
    private GoogleSignInClient mGoogleSignInClient;
    private DatabaseReference mDatabase;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        mAuth = FirebaseAuth.getInstance();
        mDatabase = FirebaseDatabase.getInstance().getReference();

        if (mAuth.getCurrentUser() != null) {
            navigateToDashboard();
            return;
        }

        initViews();
        setupGoogleSignIn();
        setupListeners();
    }

    private void initViews() {
        etPhoneNumber = findViewById(R.id.etPhoneNumber);
        btnContinueWithWhatsApp = findViewById(R.id.btnContinueWithWhatsApp);
        btnGoogleSignIn = findViewById(R.id.btnGoogleSignIn);
        progressBar = findViewById(R.id.progressBar);
        tvRegister = findViewById(R.id.tvRegister);
    }

    private void setupGoogleSignIn() {
        // PASTIKAN MENGGUNAKAN WEB CLIENT ID
        String webClientId = getString(R.string.default_web_client_id);
        // webClientId = "823421873327-ca79oneml505i3fkblo1rt68qubremc4.apps.googleusercontent.com"

        GoogleSignInOptions gso = new GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
                .requestIdToken(webClientId)
                .requestEmail()
                .requestProfile()
                .build();

        mGoogleSignInClient = GoogleSignIn.getClient(this, gso);
    }

    private void setupListeners() {
        btnContinueWithWhatsApp.setOnClickListener(v -> handleWhatsAppLogin());
        btnGoogleSignIn.setOnClickListener(v -> handleGoogleSignIn());
        tvRegister.setOnClickListener(v -> startActivity(new Intent(this, RegisterActivity.class)));
    }

    private void handleWhatsAppLogin() {
        String phoneNumber = etPhoneNumber.getText().toString().trim();

        if (TextUtils.isEmpty(phoneNumber)) {
            etPhoneNumber.setError("Nomor telepon wajib diisi");
            etPhoneNumber.requestFocus();
            return;
        }

        if (!phoneNumber.startsWith("+")) {
            phoneNumber = "+62" + phoneNumber;
        }

        progressBar.setVisibility(View.VISIBLE);
        btnContinueWithWhatsApp.setEnabled(false);

        Intent intent = new Intent(this, OTPVerificationActivity.class);
        intent.putExtra("phone_number", phoneNumber);
        startActivity(intent);
        finish();
    }

    private void handleGoogleSignIn() {
        if (mGoogleSignInClient == null) {
            Toast.makeText(this, "Google Sign-In not initialized", Toast.LENGTH_SHORT).show();
            return;
        }

        progressBar.setVisibility(View.VISIBLE);
        btnGoogleSignIn.setEnabled(false);

        Intent signInIntent = mGoogleSignInClient.getSignInIntent();
        startActivityForResult(signInIntent, RC_SIGN_IN);
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == RC_SIGN_IN) {
            try {
                Task<GoogleSignInAccount> task = GoogleSignIn.getSignedInAccountFromIntent(data);
                GoogleSignInAccount account = task.getResult(ApiException.class);

                if (account != null) {
                    firebaseAuthWithGoogle(account);
                } else {
                    Toast.makeText(this, "Account is null", Toast.LENGTH_SHORT).show();
                    progressBar.setVisibility(View.GONE);
                    btnGoogleSignIn.setEnabled(true);
                }

            } catch (ApiException e) {
                String errorMessage = getGoogleSignInErrorMessage(e.getStatusCode());
                Toast.makeText(this, "Google Sign-In failed: " + errorMessage, Toast.LENGTH_LONG).show();
                progressBar.setVisibility(View.GONE);
                btnGoogleSignIn.setEnabled(true);
                e.printStackTrace();
            }
        }
    }

    private String getGoogleSignInErrorMessage(int statusCode) {
        switch (statusCode) {
            case GoogleSignInStatusCodes.SIGN_IN_CANCELLED:
                return "Sign-in dibatalkan";
            case GoogleSignInStatusCodes.SIGN_IN_FAILED:
                return "Sign-in gagal, coba lagi";
            case GoogleSignInStatusCodes.NETWORK_ERROR:
                return "Network error, cek koneksi internet";
            case GoogleSignInStatusCodes.DEVELOPER_ERROR:
                return "Developer error. Cek SHA-1 dan OAuth Client ID";
            case GoogleSignInStatusCodes.INTERNAL_ERROR:
                return "Internal error, coba lagi";
            case GoogleSignInStatusCodes.TIMEOUT:
                return "Time out, coba lagi";
            default:
                return "Error code: " + statusCode;
        }
    }

    private void firebaseAuthWithGoogle(GoogleSignInAccount acct) {
        AuthCredential credential = GoogleAuthProvider.getCredential(acct.getIdToken(), null);

        mAuth.signInWithCredential(credential)
                .addOnCompleteListener(this, task -> {
                    progressBar.setVisibility(View.GONE);
                    btnGoogleSignIn.setEnabled(true);

                    if (task.isSuccessful()) {
                        FirebaseUser user = mAuth.getCurrentUser();
                        if (user != null) {
                            checkAndSaveUser(user, "google");
                        }
                        navigateToDashboard();
                    } else {
                        String errorMsg = task.getException() != null ?
                                task.getException().getMessage() : "Unknown error";
                        Toast.makeText(this, "Firebase Auth failed: " + errorMsg, Toast.LENGTH_LONG).show();
                    }
                });
    }

    private void checkAndSaveUser(FirebaseUser user, String provider) {
        if (user == null) return;

        String userId = user.getUid();

        mDatabase.child("users").child(userId).get()
                .addOnSuccessListener(snapshot -> {
                    if (!snapshot.exists()) {
                        saveUserToDatabase(user, provider);
                    }
                })
                .addOnFailureListener(e -> {
                    saveUserToDatabase(user, provider);
                });
    }

    private void saveUserToDatabase(FirebaseUser user, String provider) {
        if (user == null) return;

        String userId = user.getUid();
        String name = user.getDisplayName() != null ? user.getDisplayName() : "User";
        String email = user.getEmail() != null ? user.getEmail() : "";
        String phone = user.getPhoneNumber() != null ? user.getPhoneNumber() : "";
        String photo = user.getPhotoUrl() != null ? user.getPhotoUrl().toString() : "";

        User newUser = new User(userId, name, email, phone, photo, provider);
        mDatabase.child("users").child(userId).setValue(newUser);
    }

    private void navigateToDashboard() {
        Intent intent = new Intent(this, DashboardActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
        finish();
    }
}